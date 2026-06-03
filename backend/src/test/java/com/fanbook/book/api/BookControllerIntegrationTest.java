package com.fanbook.book.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.book.infrastructure.ChapterRepository;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.testsupport.MinimalEpubFactory;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class BookControllerIntegrationTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:book_controller;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/test-storage");
    }

    @Autowired
    MockMvc mockMvc;

    @Autowired
    BookRepository bookRepository;

    @Autowired
    SegmentRepository segmentRepository;

    @Autowired
    ChapterRepository chapterRepository;

    @BeforeEach
    void cleanDatabase() {
        segmentRepository.deleteAll();
        chapterRepository.deleteAll();
        bookRepository.deleteAll();
    }

    @Test
    void uploadsAndParsesEpub() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "demo.epub",
                "application/epub+zip",
                MinimalEpubFactory.create()
        );

        mockMvc.perform(multipart("/api/books").file(file).param("sourceLanguage", "en"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.title").value("Demo Book"))
                .andExpect(jsonPath("$.chapters").value(1))
                .andExpect(jsonPath("$.segments").value(3));

        assertThat(bookRepository.findAll()).hasSize(1);
        assertThat(segmentRepository.findAll()).hasSize(3);
    }

    @Test
    void uploadsWithTitleOverride() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "demo.epub",
                "application/epub+zip",
                MinimalEpubFactory.create()
        );

        mockMvc.perform(multipart("/api/books")
                        .file(file)
                        .param("sourceLanguage", "en")
                        .param("title", "Custom Dashboard Title"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.title").value("Custom Dashboard Title"));

        assertThat(bookRepository.findAll()).singleElement()
                .extracting(book -> book.getTitle())
                .isEqualTo("Custom Dashboard Title");
    }

    @Test
    void readsBookDetailForDashboard() throws Exception {
        Long bookId = uploadDemoBook();

        mockMvc.perform(get("/api/books/" + bookId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.book.id").value(bookId))
                .andExpect(jsonPath("$.book.title").value("Demo Book"))
                .andExpect(jsonPath("$.book.filename").value("demo.epub"))
                .andExpect(jsonPath("$.book.source_language").value("en"))
                .andExpect(jsonPath("$.book.title_translation_status").value("pending"))
                .andExpect(jsonPath("$.current_job").doesNotExist())
                .andExpect(jsonPath("$.chapters[0].order").value(1))
                .andExpect(jsonPath("$.chapters[0].title").value("Chapter One"))
                .andExpect(jsonPath("$.chapters[0].total_segments").value(3))
                .andExpect(jsonPath("$.chapters[0].translated_segments").value(0))
                .andExpect(jsonPath("$.chapters[0].failed_segments").value(0))
                .andExpect(jsonPath("$.artifacts").isArray());
    }

    @Test
    void listsBooksForDashboardLibrary() throws Exception {
        Long bookId = uploadDemoBook();

        mockMvc.perform(get("/api/books"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.books[0].id").value(bookId))
                .andExpect(jsonPath("$.books[0].title").value("Demo Book"))
                .andExpect(jsonPath("$.books[0].filename").value("demo.epub"))
                .andExpect(jsonPath("$.books[0].source_language").value("en"))
                .andExpect(jsonPath("$.books[0].total_segments").value(3))
                .andExpect(jsonPath("$.status_counts.total").value(1))
                .andExpect(jsonPath("$.status_counts.running").value(0))
                .andExpect(jsonPath("$.status_counts.completed").value(0))
                .andExpect(jsonPath("$.status_counts.failed").value(0));
    }

    @Test
    void updatesTranslatedTitleForDashboard() throws Exception {
        Long bookId = uploadDemoBook();

        mockMvc.perform(patch("/api/books/" + bookId + "/translated-title")
                        .contentType("application/json")
                        .content("{\"translated_title\":\"演示书\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.book.id").value(bookId))
                .andExpect(jsonPath("$.book.translated_title").value("演示书"))
                .andExpect(jsonPath("$.book.title_translation_status").value("completed"));
    }

    private Long uploadDemoBook() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "demo.epub",
                "application/epub+zip",
                MinimalEpubFactory.create()
        );
        String response = mockMvc.perform(multipart("/api/books").file(file).param("sourceLanguage", "en"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        return Long.valueOf(response.replaceAll(".*\"bookId\":(\\d+).*", "$1"));
    }
}
