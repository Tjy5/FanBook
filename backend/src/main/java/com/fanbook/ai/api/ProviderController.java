package com.fanbook.ai.api;

import com.fanbook.translation.application.TranslationRuntimeProfile;
import com.fanbook.translation.application.TranslationRuntimeSafetyService;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ProviderController {

    private final TranslationRuntimeSafetyService runtimeSafetyService;

    public ProviderController(TranslationRuntimeSafetyService runtimeSafetyService) {
        this.runtimeSafetyService = runtimeSafetyService;
    }

    @GetMapping("/api/providers")
    public ProviderProfilesResponse listProviders() {
        TranslationRuntimeProfile runtime = runtimeSafetyService.activeProfile();
        ProviderProfilesResponse.ProviderProfileDto profile = new ProviderProfilesResponse.ProviderProfileDto(
                runtime.providerName(),
                runtime.providerName(),
                runtime.modelName(),
                runtime.configured(),
                null,
                runtime.maxConcurrency(),
                1,
                true,
                runtime.endpoint(),
                runtime.usesChatCompletions(),
                runtime.thinkingMode(),
                runtime.jsonMode(),
                runtime.minRequestIntervalSeconds(),
                runtime.requestTimeoutSeconds(),
                runtime.messagingPrefetch(),
                runtime.messagingConcurrency(),
                runtime.messagingListenerAutoStartup(),
                runtime.chunkTargetCharacters(),
                runtime.maxSegmentsPerChunk(),
                runtime.maxAttemptsPerChunk(),
                runtime.paidSafetyLevel()
        );
        return new ProviderProfilesResponse(runtime.providerName(), List.of(profile));
    }
}
