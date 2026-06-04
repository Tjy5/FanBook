package com.fanbook.ai.application;

import com.fanbook.ai.domain.AiTranslationProvider;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class ProviderFactory {

    private final Map<String, AiTranslationProvider> providers;

    public ProviderFactory(List<AiTranslationProvider> providerList) {
        this.providers = providerList.stream()
                .collect(Collectors.toUnmodifiableMap(AiTranslationProvider::name, Function.identity()));
    }

    public AiTranslationProvider getProvider(String name) {
        AiTranslationProvider provider = providers.get(name);
        if (provider == null) {
            throw new FanbookException(
                    ErrorCode.PROVIDER_NOT_FOUND,
                    HttpStatus.BAD_REQUEST,
                    "Provider '" + name + "' not found."
            );
        }
        return provider;
    }
}
