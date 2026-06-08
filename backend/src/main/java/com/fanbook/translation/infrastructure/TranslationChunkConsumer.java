package com.fanbook.translation.infrastructure;

import com.fanbook.common.error.FanbookException;
import com.fanbook.translation.application.ChunkMessage;
import com.fanbook.translation.application.TranslationChunkPublisher;
import com.fanbook.translation.application.TranslationChunkDegradationService;
import com.fanbook.translation.application.TranslationChunkStateService;
import com.fanbook.translation.application.TranslationChunkWorker;
import com.fanbook.translation.application.TranslationJobAggregator;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.rabbitmq.client.Channel;
import java.io.IOException;
import java.time.OffsetDateTime;
import java.util.concurrent.atomic.AtomicInteger;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.support.AmqpHeaders;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;

@Component
public class TranslationChunkConsumer {

    private static final Logger log = LoggerFactory.getLogger(TranslationChunkConsumer.class);

    private final TranslationChunkStateService stateService;
    private final TranslationChunkWorker worker;
    private final TranslationJobAggregator aggregator;
    private final TranslationChunkPublisher chunkPublisher;
    private final TranslationJobRepository jobRepository;
    private final TranslationChunkDegradationService degradationService;
    private final TransactionTemplate transactionTemplate;
    private final TransactionTemplate afterCommitTransactionTemplate;
    private final int maxAttempts;

    public TranslationChunkConsumer(
            TranslationChunkStateService stateService,
            TranslationChunkWorker worker,
            TranslationJobAggregator aggregator,
            TranslationChunkPublisher chunkPublisher,
            TranslationJobRepository jobRepository,
            TranslationChunkDegradationService degradationService,
            PlatformTransactionManager transactionManager,
            @Value("${fanbook.translation.max-attempts-per-chunk:3}") int maxAttempts
    ) {
        this.stateService = stateService;
        this.worker = worker;
        this.aggregator = aggregator;
        this.chunkPublisher = chunkPublisher;
        this.jobRepository = jobRepository;
        this.degradationService = degradationService;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
        this.afterCommitTransactionTemplate = new TransactionTemplate(transactionManager);
        this.afterCommitTransactionTemplate.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        this.maxAttempts = maxAttempts;
    }

    @RabbitListener(
            queues = "${fanbook.translation.messaging.chunk-queue}",
            containerFactory = "manualAckRabbitListenerContainerFactory"
    )
    public void handle(
            ChunkMessage message,
            Channel channel,
            @Header(AmqpHeaders.DELIVERY_TAG) long deliveryTag
    ) throws IOException {
        ChunkDeliveryAction action = handleForTest(message);
        if (action == ChunkDeliveryAction.ACK) {
            channel.basicAck(deliveryTag, false);
            return;
        }
        channel.basicNack(deliveryTag, false, true);
    }

    public ChunkDeliveryAction handleForTest(ChunkMessage message) {
        if (isCanceled(message.jobId())) {
            return ChunkDeliveryAction.ACK;
        }
        if (!stateService.tryAcquire(message.chunkId(), workerId())) {
            return ChunkDeliveryAction.ACK;
        }
        try {
            worker.execute(message.chunkId());
            stateService.markCompleted(message.chunkId());
            aggregator.aggregate(message.jobId());
            return ChunkDeliveryAction.ACK;
        } catch (FanbookException exception) {
            handleBusinessFailure(message, exception);
            return ChunkDeliveryAction.ACK;
        } catch (RuntimeException exception) {
            log.warn("Transient chunk processing failure for chunk {}", message.chunkId(), exception);
            return ChunkDeliveryAction.NACK_REQUEUE;
        }
    }

    private boolean isCanceled(Long jobId) {
        return jobRepository.findById(jobId)
                .map(job -> job.getStatus() == TranslationJobStatus.CANCELED)
                .orElse(false);
    }

    private void handleBusinessFailure(ChunkMessage message, FanbookException exception) {
        AtomicInteger currentAttempt = new AtomicInteger(0);
        transactionTemplate.execute(status -> {
            stateService.markFailed(message.chunkId(), exception.code().value(), exception.getMessage());
            currentAttempt.set(stateService.currentAttempt(message.chunkId()));
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    if (currentAttempt.get() < maxAttempts) {
                        publishRetry(message, currentAttempt.get());
                        return;
                    }
                    degradeOrAggregateAfterRetryExhaustion(message);
                }
            });
            return null;
        });
    }

    private void publishRetry(ChunkMessage message, int currentAttempt) {
        try {
            int nextAttempt = currentAttempt + 1;
            chunkPublisher.publish(new ChunkMessage(
                    "1.0",
                    message.jobId(),
                    message.chunkId(),
                    nextAttempt,
                    "RETRY",
                    message.correlationId() + "-retry-" + nextAttempt,
                    OffsetDateTime.now()
            ));
        } catch (RuntimeException publishException) {
            log.error("Failed to publish retry chunk message for chunk {}", message.chunkId(), publishException);
        }
    }

    private void degradeOrAggregateAfterRetryExhaustion(ChunkMessage message) {
        try {
            afterCommitTransactionTemplate.executeWithoutResult(status -> {
                var retryMessages = degradationService.degrade(message.chunkId());
                if (!retryMessages.isEmpty()) {
                    chunkPublisher.publishAll(retryMessages);
                    return;
                }
                aggregator.aggregate(message.jobId());
            });
        } catch (RuntimeException aggregateException) {
            log.error("Failed to aggregate translation job {} after retry exhaustion", message.jobId(), aggregateException);
        }
    }

    private String workerId() {
        return "consumer-" + System.identityHashCode(Thread.currentThread());
    }
}
