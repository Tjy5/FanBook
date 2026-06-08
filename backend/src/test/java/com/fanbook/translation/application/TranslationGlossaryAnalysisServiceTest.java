package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.ai.domain.StructuredGlossaryAnalysisRequest;
import com.fanbook.ai.domain.StructuredGlossaryAnalysisResult;
import com.fanbook.ai.domain.StructuredGlossaryCandidateItem;
import com.fanbook.ai.infrastructure.MockAiTranslationProvider;
import com.fanbook.book.application.BookApplicationService;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.GlossaryAnalysisRequest;
import com.fanbook.translation.domain.TranslationGlossaryCandidateStatus;
import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.security.authentication.TestingAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
class TranslationGlossaryAnalysisServiceTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:translation_glossary_analysis;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/translation-glossary-analysis-storage");
        registry.add("fanbook.ai.provider", () -> "glossary-conflict");
        registry.add("fanbook.translation.glossary[0].source-term", () -> "Alice");
        registry.add("fanbook.translation.glossary[0].target-term", () -> "艾丽丝");
        registry.add("fanbook.translation.glossary[0].category", () -> "person");
        registry.add("fanbook.translation.glossary[0].note", () -> "Explicit user term wins.");
    }

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    TranslationGlossaryAnalysisService analysisService;

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void marksConfiguredGlossaryTargetMismatchAsConflictAndDoesNotAcceptIt() {
        SecurityContextHolder.getContext().setAuthentication(new TestingAuthenticationToken(
                "admin",
                "password",
                List.of(new SimpleGrantedAuthority("ROLE_ADMIN"))
        ));
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>Alice went to Wonderland.</p>
                """), "en");

        var analysis = analysisService.analyze(
                book.bookId(),
                new GlossaryAnalysisRequest("glossary-conflict", "mock-analysis", 10, true, null)
        );

        assertThat(analysis.candidates())
                .anySatisfy(candidate -> {
                    assertThat(candidate.sourceTerm()).isEqualTo("Alice");
                    assertThat(candidate.status()).isEqualTo(TranslationGlossaryCandidateStatus.CONFLICT.name());
                })
                .anySatisfy(candidate -> {
                    assertThat(candidate.sourceTerm()).isEqualTo("Wonderland");
                    assertThat(candidate.status()).isEqualTo(TranslationGlossaryCandidateStatus.CANDIDATE.name());
                });

        var imported = analysisService.acceptCandidatesForCurrentUser(book.bookId());

        assertThat(imported.acceptedCandidates()).isEqualTo(1);
        assertThat(imported.conflicts()).isEqualTo(1);
    }

    @TestConfiguration
    static class GlossaryConfig {
        @Bean
        @Primary
        ConflictGlossaryProvider conflictGlossaryProvider() {
            return new ConflictGlossaryProvider();
        }
    }

    static class ConflictGlossaryProvider extends MockAiTranslationProvider {
        @Override
        public String name() {
            return "glossary-conflict";
        }

        @Override
        public StructuredGlossaryAnalysisResult analyzeGlossary(StructuredGlossaryAnalysisRequest request, String modelName) {
            Long segmentId = request.items().isEmpty() ? null : request.items().getLast().segmentId();
            return new StructuredGlossaryAnalysisResult(
                    List.of(
                            new StructuredGlossaryCandidateItem("Alice", "爱丽丝", "person", "Conflicts with configured glossary.", segmentId),
                            new StructuredGlossaryCandidateItem("Wonderland", "仙境", "place", "New recurring location.", segmentId)
                    ),
                    name(),
                    modelName
            );
        }
    }
}
