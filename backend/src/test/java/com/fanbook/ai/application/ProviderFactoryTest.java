package com.fanbook.ai.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fanbook.ai.infrastructure.MockAiTranslationProvider;
import java.util.List;
import org.junit.jupiter.api.Test;

class ProviderFactoryTest {

    @Test
    void returnsProviderByName() {
        ProviderFactory factory = new ProviderFactory(List.of(new MockAiTranslationProvider()));

        assertThat(factory.getProvider("mock").name()).isEqualTo("mock");
    }

    @Test
    void rejectsUnknownProvider() {
        ProviderFactory factory = new ProviderFactory(List.of(new MockAiTranslationProvider()));

        assertThatThrownBy(() -> factory.getProvider("missing"))
                .hasMessageContaining("Provider 'missing' not found");
    }
}
