package com.fanbook.ai.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.ai.domain.StructuredTranslationRequest;
import com.fanbook.ai.domain.StructuredTranslationSourceItem;
import com.fanbook.common.error.FanbookException;
import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class OpenAiCompatibleProviderTest {

    @Test
    void parsesStructuredResponseItemsFromOutputText() {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("https://fake.example/v1/responses"))
                .andExpect(header("Authorization", "Bearer test-key"))
                .andRespond(withSuccess("""
                        {
                          "output_text": "{\\"items\\":[{\\"segmentId\\":1,\\"translatedText\\":\\"你好\\"}]}"
                        }
                        """, MediaType.APPLICATION_JSON));
        OpenAiCompatibleProvider provider = new OpenAiCompatibleProvider(
                builder,
                JsonMapper.builder().build(),
                new OpenAiCompatibleProperties(
                        "https://fake.example/v1",
                        "test-key",
                        "gpt-test",
                        Duration.ofSeconds(30),
                        2
                )
        );

        var result = provider.translateChunk(new StructuredTranslationRequest(
                "en",
                "zh",
                "Demo Book",
                "Chapter One",
                List.of(new StructuredTranslationSourceItem(1L, "Hello"))
        ));

        assertThat(result.providerName()).isEqualTo("openai-compatible");
        assertThat(result.modelName()).isEqualTo("gpt-test");
        assertThat(result.items()).hasSize(1);
        assertThat(result.items().getFirst().translatedText()).isEqualTo("你好");
        server.verify();
    }

    @Test
    void rejectsMissingApiKey() {
        OpenAiCompatibleProvider provider = new OpenAiCompatibleProvider(
                RestClient.builder(),
                JsonMapper.builder().build(),
                new OpenAiCompatibleProperties(
                        "https://fake.example/v1",
                        "",
                        "gpt-test",
                        Duration.ofSeconds(30),
                        2
                )
        );

        assertThatThrownBy(() -> provider.translateChunk(new StructuredTranslationRequest(
                "en",
                "zh",
                "Demo",
                "Chapter",
                List.of()
        )))
                .isInstanceOf(FanbookException.class)
                .hasMessageContaining("API key");
    }
}
