package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.ai.infrastructure.OpenAiCompatibleProperties;
import com.fanbook.translation.config.TranslationChunkPlanningProperties;
import com.fanbook.translation.config.TranslationMessagingProperties;
import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.mock.env.MockEnvironment;

class TranslationRuntimeSafetyServiceTest {

    @Test
    void mockProviderIsCheapAndSafe() {
        TranslationRuntimeProfile profile = service("mock", properties("", "mock-translator", "responses", "", 2, Duration.ZERO), messaging(4, 2, true), 3)
                .profile(null, null);

        assertThat(profile.realProvider()).isFalse();
        assertThat(profile.configured()).isTrue();
        assertThat(profile.safeToStart()).isTrue();
        assertThat(profile.paidSafetyLevel()).isEqualTo("mock");
        assertThat(profile.warnings()).isEmpty();
    }

    @Test
    void openAiCompatibleWithoutKeyIsUnsafe() {
        TranslationRuntimeProfile profile = service("openai-compatible", properties("", "gpt-5", "responses", "", 1, Duration.ofSeconds(6)), messaging(1, 1, true), 1)
                .profile(null, null);

        assertThat(profile.realProvider()).isTrue();
        assertThat(profile.configured()).isFalse();
        assertThat(profile.safeToStart()).isFalse();
        assertThat(profile.paidSafetyLevel()).isEqualTo("unsafe");
        assertThat(profile.warnings()).anySatisfy(warning -> assertThat(warning).contains("FANBOOK_AI_API_KEY"));
    }

    @Test
    void deepSeekLikePaidProfileIsSafeWhenChatCompletionsThinkingDisabledAndSlowSingleConcurrency() {
        TranslationRuntimeProfile profile = service(
                "openai-compatible",
                properties("test-key", "deepseek-v4-flash", "chat-completions", "disabled", 1, Duration.ofSeconds(6)),
                messaging(1, 1, true),
                1
        ).profile(null, null);

        assertThat(profile.configured()).isTrue();
        assertThat(profile.realProvider()).isTrue();
        assertThat(profile.safeToStart()).isTrue();
        assertThat(profile.paidSafetyLevel()).isEqualTo("safe");
        assertThat(profile.usesChatCompletions()).isTrue();
        assertThat(profile.thinkingMode()).isEqualTo("disabled");
        assertThat(profile.warnings()).isEmpty();
        assertThat(profile.recommendations()).anySatisfy(recommendation -> assertThat(recommendation).contains("FANBOOK_AI_MIN_REQUEST_INTERVAL=6s"));
    }

    @Test
    void highConcurrencyAndNoPacingAreUnsafeForPaidProvider() {
        TranslationRuntimeProfile profile = service(
                "openai-compatible",
                properties("test-key", "gpt-5", "responses", "", 3, Duration.ZERO),
                messaging(2, 2, true),
                3
        ).profile(null, null);

        assertThat(profile.safeToStart()).isFalse();
        assertThat(profile.paidSafetyLevel()).isEqualTo("unsafe");
        assertThat(profile.warnings()).anySatisfy(warning -> assertThat(warning).contains("Provider max concurrency"));
        assertThat(profile.warnings()).anySatisfy(warning -> assertThat(warning).contains("Messaging concurrency"));
        assertThat(profile.warnings()).anySatisfy(warning -> assertThat(warning).contains("Messaging prefetch"));
        assertThat(profile.warnings()).anySatisfy(warning -> assertThat(warning).contains("minimum request interval"));
    }

    @Test
    void disabledListenerIsUnsafeForFrontendAsyncPath() {
        TranslationRuntimeProfile profile = service(
                "openai-compatible",
                properties("test-key", "gpt-5", "responses", "", 1, Duration.ofSeconds(6)),
                messaging(1, 1, false),
                1
        ).profile(null, null);

        assertThat(profile.safeToStart()).isFalse();
        assertThat(profile.warnings()).anySatisfy(warning -> assertThat(warning).contains("listener auto-startup is disabled"));
    }

    private static TranslationRuntimeSafetyService service(
            String providerName,
            OpenAiCompatibleProperties properties,
            TranslationMessagingProperties messagingProperties,
            int maxAttemptsPerChunk
    ) {
        MockEnvironment environment = new MockEnvironment();
        environment.setProperty("fanbook.ai.provider", providerName);
        return new TranslationRuntimeSafetyService(
                environment,
                properties,
                messagingProperties,
                new TranslationChunkPlanningProperties(2500, 16, 4, 12, List.of()),
                maxAttemptsPerChunk
        );
    }

    private static OpenAiCompatibleProperties properties(
            String apiKey,
            String model,
            String endpoint,
            String thinkingMode,
            int maxConcurrency,
            Duration minRequestInterval
    ) {
        return new OpenAiCompatibleProperties(
                "https://api.test/v1",
                apiKey,
                model,
                Duration.ofSeconds(240),
                maxConcurrency,
                endpoint,
                minRequestInterval,
                thinkingMode,
                true
        );
    }

    private static TranslationMessagingProperties messaging(int prefetch, int concurrency, boolean listenerAutoStartup) {
        return new TranslationMessagingProperties(
                "fanbook.jobs",
                "translation.chunk.queue",
                "translation.chunk.retry",
                "translation.chunk.dlq",
                "translation.chunk",
                prefetch,
                concurrency,
                listenerAutoStartup
        );
    }
}
