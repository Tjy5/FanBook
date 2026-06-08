package com.fanbook.paid;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.ai.domain.AiTranslationProvider;
import com.fanbook.ai.domain.StructuredGlossaryAnalysisRequest;
import com.fanbook.ai.domain.StructuredGlossaryAnalysisResult;
import com.fanbook.ai.domain.StructuredTranslationRequest;
import com.fanbook.ai.domain.StructuredTranslationResult;
import com.fanbook.ai.domain.StructuredTranslationReviewRequest;
import com.fanbook.ai.application.ProviderFactory;
import com.fanbook.book.api.BookResponse;
import com.fanbook.book.application.BookApplicationService;
import com.fanbook.book.application.EpubParser;
import com.fanbook.book.application.ParsedBook;
import com.fanbook.book.application.SegmentInlineMarkup;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.domain.SegmentStatus;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.storage.StorageService;
import com.fanbook.export.application.ConsistencyReportService;
import com.fanbook.export.application.ExportService;
import com.fanbook.export.domain.ExportArtifactEntity;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.api.TranslationJobResponse;
import com.fanbook.translation.application.TranslationJobExecutor;
import com.fanbook.translation.application.TranslationJobService;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.transaction.support.TransactionTemplate;

@SpringBootTest
@ActiveProfiles("local")
@EnabledIfSystemProperty(named = "fanbook.paid.deepseek.translation-test", matches = "true")
class PaidDeepSeekBookTranslationTest {

    private static final String RUN_ID = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss").format(LocalDateTime.now());
    private static final Path WORKSPACE_ROOT = workspaceRoot();
    private static final Path TEST_ROOT = WORKSPACE_ROOT.resolve("test");
    private static final Path SOURCE_EPUB = TEST_ROOT.resolve("Little Prince.epub");
    private static final Path REFERENCE_EPUB = TEST_ROOT.resolve("小王子.epub");
    private static final Path ENV_FILE = TEST_ROOT.resolve(".env");
    private static final Path RUN_ROOT = TEST_ROOT.resolve("outputs").resolve(RUN_ID);
    private static final Path STORAGE_ROOT = RUN_ROOT.resolve("storage");
    private static final Path DATABASE_ROOT = RUN_ROOT.resolve("h2").resolve("fanbook-paid");
    private static final Path PROGRESS_LOG = RUN_ROOT.resolve("paid-run-progress.log");
    private static final ObjectMapper OBJECT_MAPPER = JsonMapper.builder().build();

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    TranslationJobService translationJobService;

    @Autowired
    TranslationJobExecutor translationJobExecutor;

    @Autowired
    TranslationJobRepository jobRepository;

    @Autowired
    TranslationChunkRepository chunkRepository;

    @Autowired
    SegmentRepository segmentRepository;

    @Autowired
    ExportService exportService;

    @Autowired
    ConsistencyReportService reportService;

    @Autowired
    StorageService storageService;

    @Autowired
    EpubParser epubParser;

    @Autowired
    TransactionTemplate transactionTemplate;

    @DynamicPropertySource
    static void paidProperties(DynamicPropertyRegistry registry) {
        PaidConfig config = paidConfig();
        registry.add("spring.datasource.url", () -> "jdbc:h2:file:" + jdbcPath(DATABASE_ROOT)
                + ";MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_ON_EXIT=FALSE");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("spring.data.redis.repositories.enabled", () -> "false");
        registry.add("fanbook.storage.root", () -> STORAGE_ROOT.toString());
        registry.add("fanbook.ai.provider", () -> "openai-compatible");
        registry.add("fanbook.ai.api-key", config::apiKey);
        registry.add("fanbook.ai.base-url", config::baseUrl);
        registry.add("fanbook.ai.model", config::model);
        registry.add("fanbook.ai.endpoint", () -> "chat-completions");
        registry.add("fanbook.ai.thinking-mode", () -> "disabled");
        registry.add("fanbook.ai.json-mode", () -> "true");
        registry.add("fanbook.ai.max-concurrency", () -> "1");
        registry.add("fanbook.ai.min-request-interval", () -> "6s");
        registry.add("fanbook.ai.request-timeout", () -> "240s");
        registry.add("fanbook.translation.messaging.prefetch", () -> "1");
        registry.add("fanbook.translation.messaging.concurrency", () -> "1");
        registry.add("fanbook.translation.messaging.listener-auto-startup", () -> "false");
        registry.add("fanbook.translation.max-attempts-per-chunk", () -> "1");
        registry.add("fanbook.translation.recovery.scan-delay", () -> "3600s");
        registry.add("fanbook.translation.chunk-target-characters", () -> "2500");
        registry.add("fanbook.translation.max-segments-per-chunk", () -> "16");
        registry.add("fanbook.translation.context-window-segments", () -> "4");
        registry.add("fanbook.translation.prompt.name", () -> "paid-little-prince-zh");
        registry.add("fanbook.translation.prompt.version", () -> "v1");
        registry.add("fanbook.translation.prompt.style-instruction", () -> """
                Translate into fluent Simplified Chinese literary prose. Keep the clear, gentle,
                poetic voice of a children's fable while preserving meaning and narrative rhythm.
                """);
        registry.add("fanbook.translation.prompt.translation-instruction", () -> """
                Use established Chinese renderings for widely known Little Prince names and concepts
                when they fit the source. Do not summarize, omit, or add commentary.
                """);
    }

    @Test
    void translatesLittlePrinceWithPaidDeepSeekModel() throws Exception {
        Files.createDirectories(RUN_ROOT);
        appendProgress("run " + RUN_ID + " started");

        assertThat(Files.isRegularFile(SOURCE_EPUB)).as("source EPUB exists").isTrue();
        assertThat(Files.isRegularFile(REFERENCE_EPUB)).as("reference EPUB exists").isTrue();

        PaidConfig config = paidConfig();
        ParsedBook sourcePreview = epubParser.parse(Files.readAllBytes(SOURCE_EPUB));
        ParsedBook referencePreview = epubParser.parse(Files.readAllBytes(REFERENCE_EPUB));
        appendProgress("source chapters=" + sourcePreview.chapters().size()
                + " source segments=" + segmentCount(sourcePreview));
        appendProgress("reference chapters=" + referencePreview.chapters().size()
                + " reference segments=" + segmentCount(referencePreview));

        BookResponse book = bookApplicationService.upload(
                SOURCE_EPUB.getFileName().toString(),
                Files.readAllBytes(SOURCE_EPUB),
                "en",
                sourcePreview.title()
        );
        TranslationJobResponse job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("openai-compatible", config.model()),
                "paid-test"
        );
        int chunks = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).size();
        appendProgress("bookId=" + book.bookId() + " jobId=" + job.jobId()
                + " totalSegments=" + job.totalSegments() + " chunks=" + chunks);

        translationJobExecutor.runJob(job.jobId());

        var completedJob = jobRepository.findById(job.jobId()).orElseThrow();
        appendProgress("job status=" + completedJob.getStatus()
                + " translatedSegments=" + completedJob.getTranslatedSegments()
                + " failedSegments=" + completedJob.getFailedSegments()
                + " errorSummary=" + diagnosticText(completedJob.getErrorSummary()));
        chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).stream()
                .filter(chunk -> chunk.getStatus() == TranslationChunkStatus.FAILED)
                .findFirst()
                .ifPresent(chunk -> appendProgress("failed chunk id=" + chunk.getId()
                        + " order=" + chunk.getChunkOrder()
                        + " attempts=" + chunk.getAttemptCount()
                        + " errorCode=" + diagnosticText(chunk.getLastErrorCode())
                        + " errorMessage=" + diagnosticText(chunk.getLastErrorMessage())));
        assertThat(completedJob.getStatus()).isEqualTo(TranslationJobStatus.COMPLETED);

        ExportArtifactEntity zh = exportService.exportZh(book.bookId());
        ExportArtifactEntity bilingual = exportService.exportBilingual(book.bookId());
        ExportArtifactEntity reportJson = reportService.generateJson(book.bookId());
        ExportArtifactEntity reportMd = reportService.generateMarkdown(book.bookId());

        Path zhPath = copyArtifact(zh, "little-prince.zh.deepseek-v4-flash.epub");
        Path bilingualPath = copyArtifact(bilingual, "little-prince.bilingual.deepseek-v4-flash.epub");
        Path reportJsonPath = copyArtifact(reportJson, "consistency.json");
        Path reportMdPath = copyArtifact(reportMd, "consistency.md");
        Path summaryPath = RUN_ROOT.resolve("paid-run-summary.md");
        long completedChunks = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).stream()
                .filter(chunk -> chunk.getStatus() == TranslationChunkStatus.COMPLETED)
                .count();
        Files.writeString(
                summaryPath,
                summary(
                        book,
                        completedJob.getId(),
                        chunks,
                        completedChunks,
                        ProgressLoggingProvider.completedTranslateRequests(),
                        config,
                        sourcePreview,
                        referencePreview,
                        zhPath,
                        bilingualPath,
                        reportJsonPath,
                        reportMdPath
                ),
                StandardCharsets.UTF_8
        );
        appendProgress("artifacts copied to " + RUN_ROOT);

        assertThat(Files.size(zhPath)).isGreaterThan(0);
        assertThat(Files.size(bilingualPath)).isGreaterThan(0);
        assertThat(Files.size(reportJsonPath)).isGreaterThan(0);
        assertThat(Files.size(reportMdPath)).isGreaterThan(0);
    }

    private Path copyArtifact(ExportArtifactEntity artifact, String filename) throws Exception {
        Path target = RUN_ROOT.resolve(filename);
        Files.write(target, storageService.read(artifact.getObjectKey()));
        return target;
    }

    private String summary(
            BookResponse book,
            Long jobId,
            int chunks,
            long completedChunks,
            int completedTranslateRequests,
            PaidConfig config,
            ParsedBook sourcePreview,
            ParsedBook referencePreview,
            Path zhPath,
            Path bilingualPath,
            Path reportJsonPath,
            Path reportMdPath
    ) throws Exception {
        SummaryStats stats = summaryStats(book.bookId());
        List<String> referenceSamples = referencePreview.chapters().stream()
                .flatMap(chapter -> chapter.segments().stream())
                .limit(8)
                .map(segment -> "- " + snippet(segment.sourceText(), 80))
                .toList();
        ReportShape report = OBJECT_MAPPER.readValue(Files.readAllBytes(reportJsonPath), ReportShape.class);

        return """
                # Paid DeepSeek Translation Run

                - Run ID: %s
                - Provider: openai-compatible
                - Model: %s
                - Endpoint mode: chat-completions
                - Thinking mode: disabled
                - Request concurrency: 1
                - Minimum request interval: 6s
                - Book ID: %d
                - Job ID: %d
                - Source title: %s
                - Source chapters: %d
                - Source parser segments: %d
                - Reference title: %s
                - Reference chapters: %d
                - Reference parser segments: %d
                - Translation chunks: %d
                - Completed chunks: %d / %d
                - Provider translate requests completed: %d
                - Translated segments: %d / %d
                - Failed segments: %d
                - Consistency quality score: %d
                - Consistency warnings: %d
                - Term warnings: %d

                ## Artifacts

                - Chinese EPUB: `%s`
                - Bilingual EPUB: `%s`
                - Consistency JSON: `%s`
                - Consistency Markdown: `%s`
                - Progress log: `%s`

                ## Generated Translation Samples

                %s

                ## Reference EPUB Samples

                These reference snippets are not aligned segment-by-segment; they are a compact local style reference from `test/小王子.epub`.

                %s
                """.formatted(
                RUN_ID,
                config.model(),
                book.bookId(),
                jobId,
                snippet(sourcePreview.title(), 80),
                sourcePreview.chapters().size(),
                segmentCount(sourcePreview),
                snippet(referencePreview.title(), 80),
                referencePreview.chapters().size(),
                segmentCount(referencePreview),
                chunks,
                completedChunks,
                chunks,
                completedTranslateRequests,
                stats.translatedSegments(),
                book.segments(),
                stats.failedSegments(),
                report.qualityScore(),
                report.warnings() == null ? 0 : report.warnings().size(),
                report.termWarnings() == null ? 0 : report.termWarnings().size(),
                zhPath,
                bilingualPath,
                reportJsonPath,
                reportMdPath,
                PROGRESS_LOG,
                stats.translatedSamples().isEmpty() ? "- No translated samples were available." : String.join("\n", stats.translatedSamples()),
                referenceSamples.isEmpty() ? "- No reference samples were available." : String.join("\n", referenceSamples)
        );
    }

    private SummaryStats summaryStats(Long bookId) {
        return transactionTemplate.execute(status -> {
            List<SegmentEntity> segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(bookId);
            long translated = segments.stream().filter(segment -> segment.getStatus() == SegmentStatus.TRANSLATED).count();
            long failed = segments.stream().filter(segment -> segment.getStatus() == SegmentStatus.FAILED).count();
            List<String> samples = segments.stream()
                    .filter(segment -> segment.getTranslatedText() != null && !segment.getTranslatedText().isBlank())
                    .limit(8)
                    .map(segment -> "- Segment " + segment.getId() + ": "
                            + snippet(SegmentInlineMarkup.displayTranslatedText(segment), 80))
                    .toList();
            return new SummaryStats(translated, failed, samples);
        });
    }

    private static int segmentCount(ParsedBook book) {
        return book.chapters().stream().mapToInt(chapter -> chapter.segments().size()).sum();
    }

    private static String snippet(String text, int limit) {
        if (text == null) {
            return "";
        }
        String compact = text.replaceAll("\\s+", " ").trim();
        if (compact.length() <= limit) {
            return compact;
        }
        return compact.substring(0, Math.max(0, limit - 3)) + "...";
    }

    private static String diagnosticText(String text) {
        if (text == null || text.isBlank()) {
            return "";
        }
        String compact = text.replaceAll("\\s+", " ").trim();
        int limit = 500;
        if (compact.length() <= limit) {
            return compact;
        }
        return compact.substring(0, limit - 3) + "...";
    }

    private static PaidConfig paidConfig() {
        try {
            List<String> lines = Files.readAllLines(ENV_FILE, StandardCharsets.UTF_8).stream()
                    .map(String::trim)
                    .filter(line -> !line.isBlank())
                    .collect(Collectors.toCollection(ArrayList::new));
            if (lines.size() < 3) {
                throw new IllegalStateException("test/.env must contain API key, base URL, and model on three non-empty lines.");
            }
            return new PaidConfig(lines.get(0), lines.get(1), lines.get(2));
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to read paid DeepSeek config from test/.env.", exception);
        }
    }

    private static void appendProgress(String line) {
        try {
            Files.createDirectories(RUN_ROOT);
            Files.writeString(
                    PROGRESS_LOG,
                    LocalDateTime.now() + " " + line + System.lineSeparator(),
                    StandardCharsets.UTF_8,
                    java.nio.file.StandardOpenOption.CREATE,
                    java.nio.file.StandardOpenOption.APPEND
            );
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to write paid run progress.", exception);
        }
    }

    private static Path workspaceRoot() {
        Path cwd = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
        return "backend".equals(cwd.getFileName().toString()) ? cwd.getParent() : cwd;
    }

    private static String jdbcPath(Path path) {
        return path.toAbsolutePath().normalize().toString().replace('\\', '/');
    }

    private record PaidConfig(String apiKey, String baseUrl, String model) {
        private PaidConfig {
            if (apiKey == null || apiKey.isBlank()) {
                throw new IllegalStateException("Paid API key is blank.");
            }
            if (baseUrl == null || baseUrl.isBlank()) {
                throw new IllegalStateException("Paid base URL is blank.");
            }
            if (model == null || model.isBlank()) {
                throw new IllegalStateException("Paid model is blank.");
            }
        }
    }

    private record ReportShape(
            int qualityScore,
            List<Object> warnings,
            List<Object> termWarnings
    ) {
    }

    private record SummaryStats(
            long translatedSegments,
            long failedSegments,
            List<String> translatedSamples
    ) {
    }

    @TestConfiguration
    static class ProgressLoggingProviderConfig {

        @Bean
        @Primary
        ProviderFactory paidProgressProviderFactory(List<AiTranslationProvider> providerList) {
            return new ProviderFactory(providerList.stream()
                    .map(provider -> (AiTranslationProvider) new ProgressLoggingProvider(provider))
                    .toList());
        }
    }

    private static class ProgressLoggingProvider implements AiTranslationProvider {

        private static final AtomicInteger REQUESTS = new AtomicInteger();
        private static final AtomicInteger COMPLETED_TRANSLATE_REQUESTS = new AtomicInteger();

        private final AiTranslationProvider delegate;

        ProgressLoggingProvider(AiTranslationProvider delegate) {
            this.delegate = delegate;
        }

        @Override
        public String name() {
            return delegate.name();
        }

        @Override
        public StructuredTranslationResult translateChunk(StructuredTranslationRequest request, String modelName) {
            int requestNumber = REQUESTS.incrementAndGet();
            appendProgress("provider request " + requestNumber + " translate started provider=" + name());
            try {
                StructuredTranslationResult result = delegate.translateChunk(request, modelName);
                COMPLETED_TRANSLATE_REQUESTS.incrementAndGet();
                appendProgress("provider request " + requestNumber + " translate completed items=" + result.items().size());
                return result;
            } catch (RuntimeException exception) {
                appendProgress("provider request " + requestNumber + " translate failed");
                throw exception;
            }
        }

        @Override
        public StructuredGlossaryAnalysisResult analyzeGlossary(StructuredGlossaryAnalysisRequest request, String modelName) {
            int requestNumber = REQUESTS.incrementAndGet();
            appendProgress("provider request " + requestNumber + " glossary started provider=" + name());
            try {
                StructuredGlossaryAnalysisResult result = delegate.analyzeGlossary(request, modelName);
                appendProgress("provider request " + requestNumber + " glossary completed candidates=" + result.candidates().size());
                return result;
            } catch (RuntimeException exception) {
                appendProgress("provider request " + requestNumber + " glossary failed");
                throw exception;
            }
        }

        @Override
        public StructuredTranslationResult reviewTranslations(StructuredTranslationReviewRequest request, String modelName) {
            int requestNumber = REQUESTS.incrementAndGet();
            appendProgress("provider request " + requestNumber + " review started provider=" + name());
            try {
                StructuredTranslationResult result = delegate.reviewTranslations(request, modelName);
                appendProgress("provider request " + requestNumber + " review completed items=" + result.items().size());
                return result;
            } catch (RuntimeException exception) {
                appendProgress("provider request " + requestNumber + " review failed");
                throw exception;
            }
        }

        static int completedTranslateRequests() {
            return COMPLETED_TRANSLATE_REQUESTS.get();
        }
    }
}
