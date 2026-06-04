package com.fanbook.reader.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.book.infrastructure.ChapterRepository;
import com.fanbook.testsupport.MinimalEpubFactory;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class ReaderControllerIntegrationTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:reader_controller;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/reader-controller-storage");
    }

    @Autowired
    MockMvc mockMvc;

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    ChapterRepository chapterRepository;

    @Test
    void returnsChapterSegmentsForReader() throws Exception {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var chapter = chapterRepository.findByBookIdOrderByChapterOrderAsc(book.bookId()).getFirst();

        mockMvc.perform(get("/api/books/" + book.bookId() + "/chapters/" + chapter.getId() + "/segments")
                        .param("mode", "bilingual"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.chapterId").value(chapter.getId()))
                .andExpect(jsonPath("$.segments[0].sourceText").exists())
                .andExpect(jsonPath("$.segments[0].translationStatus").exists());
    }
}
