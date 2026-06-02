package com.fanbook.book.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.testsupport.MinimalEpubFactory;
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
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:book_controller;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
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
}
