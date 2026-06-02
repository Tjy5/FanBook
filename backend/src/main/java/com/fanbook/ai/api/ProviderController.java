package com.fanbook.ai.api;

import com.fanbook.ai.infrastructure.OpenAiCompatibleProperties;
import java.util.List;
import org.springframework.core.env.Environment;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ProviderController {

    private final Environment environment;
    private final OpenAiCompatibleProperties properties;

    public ProviderController(Environment environment, OpenAiCompatibleProperties properties) {
        this.environment = environment;
        this.properties = properties;
    }

    @GetMapping("/api/providers")
    public ProviderProfilesResponse listProviders() {
        String providerName = normalizedProviderName();
        boolean configured = !"openai-compatible".equals(providerName) || StringUtils.hasText(properties.apiKey());
        ProviderProfilesResponse.ProviderProfileDto profile = new ProviderProfilesResponse.ProviderProfileDto(
                providerName,
                providerName,
                properties.model(),
                configured,
                null,
                properties.maxConcurrency(),
                1,
                true
        );
        return new ProviderProfilesResponse(providerName, List.of(profile));
    }

    private String normalizedProviderName() {
        String configuredProvider = environment.getProperty("fanbook.ai.provider", "mock");
        if (!StringUtils.hasText(configuredProvider)) {
            return "mock";
        }
        return configuredProvider.trim();
    }
}
