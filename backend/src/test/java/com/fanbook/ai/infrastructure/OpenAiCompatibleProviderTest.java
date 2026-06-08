package com.fanbook.ai.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.ai.domain.StructuredTranslationContextItem;
import com.fanbook.ai.domain.StructuredTranslationGlossaryItem;
import com.fanbook.ai.domain.StructuredTranslationReviewItem;
import com.fanbook.ai.domain.StructuredTranslationReviewRequest;
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
                .andExpect(content().string(containsString("Do not merge, split, omit, or reorder segments.")))
                .andExpect(content().string(containsString("Use glossary entries as terminology/name constraints.")))
                .andExpect(content().string(containsString("\\\"context\\\"")))
                .andExpect(content().string(containsString("\\\"glossary\\\"")))
                .andExpect(content().string(containsString("\\\"sourceTerm\\\":\\\"Alice\\\"")))
                .andExpect(content().string(containsString("\\\"targetTerm\\\":\\\"艾丽丝\\\"")))
                .andExpect(content().string(containsString("\\\"translatedText\\\":\\\"上下文\\\"")))
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
                List.of(new StructuredTranslationContextItem(10L, "Context", "上下文")),
                List.of(new StructuredTranslationGlossaryItem("Alice", "艾丽丝", "person", "Use this name consistently.")),
                List.of(new StructuredTranslationSourceItem(1L, "Hello"))
        ));

        assertThat(result.providerName()).isEqualTo("openai-compatible");
        assertThat(result.modelName()).isEqualTo("gpt-test");
        assertThat(result.items()).hasSize(1);
        assertThat(result.items().getFirst().translatedText()).isEqualTo("你好");
        server.verify();
    }

    @Test
    void usesRequestedModelWhenProvided() {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("https://fake.example/v1/responses"))
                .andExpect(content().string(containsString("\"model\":\"job-model\"")))
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
        ), "job-model");

        assertThat(result.modelName()).isEqualTo("job-model");
        server.verify();
    }

    @Test
    void sendsInlinePlaceholderRulesOnlyWhenRequestContainsPlaceholderTokens() {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("https://fake.example/v1/responses"))
                .andExpect(content().string(containsString("Inline XHTML placeholder rules")))
                .andExpect(content().string(containsString("\\\"sourceText\\\":\\\"Hello [id0]bright[id1] world.\\\"")))
                .andRespond(withSuccess("""
                        {
                          "output_text": "{\\"items\\":[{\\"segmentId\\":1,\\"translatedText\\":\\"你好 [id0]明亮[id1] 世界\\"}]}"
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
                List.of(new StructuredTranslationSourceItem(1L, "Hello [id0]bright[id1] world."))
        ));

        assertThat(result.items().getFirst().translatedText()).isEqualTo("你好 [id0]明亮[id1] 世界");
        server.verify();
    }

    @Test
    void sendsDedicatedReviewInstructions() {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("https://fake.example/v1/responses"))
                .andExpect(content().string(containsString("Review existing target-language book translations")))
                .andExpect(content().string(containsString("make the smallest correction")))
                .andExpect(content().string(containsString("\\\"qualityScore\\\":45")))
                .andExpect(content().string(containsString("\\\"warnings\\\":[\\\"source_repeated_in_translation\\\"]")))
                .andRespond(withSuccess("""
                        {
                          "output_text": "{\\"items\\":[{\\"segmentId\\":1,\\"translatedText\\":\\"审校后译文\\"}]}"
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

        var result = provider.reviewTranslations(new StructuredTranslationReviewRequest(
                "en",
                "zh",
                "Demo Book",
                "Chapter One",
                List.of(),
                List.of(new StructuredTranslationReviewItem(
                        1L,
                        "Alice went to Wonderland.",
                        "Alice went to Wonderland. 爱丽丝去了仙境。",
                        45,
                        List.of("source_repeated_in_translation")
                ))
        ));

        assertThat(result.items().getFirst().translatedText()).isEqualTo("审校后译文");
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
