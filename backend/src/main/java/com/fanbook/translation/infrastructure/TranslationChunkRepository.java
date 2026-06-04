package com.fanbook.translation.infrastructure;

import com.fanbook.translation.domain.TranslationChunkEntity;
import com.fanbook.translation.domain.TranslationChunkStatus;
import java.time.OffsetDateTime;
import java.util.Collection;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;

public interface TranslationChunkRepository extends JpaRepository<TranslationChunkEntity, Long> {
    List<TranslationChunkEntity> findByJobIdOrderByChunkOrderAsc(Long jobId);

    List<TranslationChunkEntity> findByJobIdAndStatusInOrderByChunkOrderAsc(Long jobId, Collection<TranslationChunkStatus> statuses);

    @Modifying
    @Query("""
            update TranslationChunkEntity chunk
            set chunk.status = com.fanbook.translation.domain.TranslationChunkStatus.RUNNING,
                chunk.attemptCount = chunk.attemptCount + 1,
                chunk.startedAt = :now,
                chunk.lockedUntil = :lockedUntil,
                chunk.workerId = :workerId
            where chunk.id = :chunkId
              and chunk.attemptCount < :maxAttempts
              and (
                  chunk.status in (com.fanbook.translation.domain.TranslationChunkStatus.PENDING, com.fanbook.translation.domain.TranslationChunkStatus.FAILED)
                  or (
                      chunk.status = com.fanbook.translation.domain.TranslationChunkStatus.RUNNING
                      and (chunk.lockedUntil is null or chunk.lockedUntil < :now)
                  )
              )
            """)
    int acquireLease(Long chunkId, OffsetDateTime now, OffsetDateTime lockedUntil, String workerId, int maxAttempts);

    List<TranslationChunkEntity> findByStatusAndLockedUntilBefore(TranslationChunkStatus status, OffsetDateTime lockedUntil);

    long countByJobIdAndStatus(Long jobId, TranslationChunkStatus status);
}
