package com.fanbook.reader.api;

import static com.fanbook.testsupport.SecurityMockMvcSupport.member;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fanbook.auth.domain.UserEntity;
import com.fanbook.auth.domain.UserRole;
import com.fanbook.auth.infrastructure.UserRepository;
import com.fanbook.book.application.BookApplicationService;
import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.book.infrastructure.ChapterRepository;
import com.fanbook.testsupport.MinimalEpubFactory;
import java.util.Set;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

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

    @Autowired
    BookRepository bookRepository;

    @Autowired
    UserRepository userRepository;

    private UserEntity memberUser;

    @BeforeEach
    void seedUser() {
        bookRepository.deleteAll();
        userRepository.deleteAll();
        memberUser = userRepository.save(new UserEntity(
                "member",
                "member@example.test",
                "{noop}password",
                Set.of(UserRole.MEMBER)
        ));
    }

    @Test
    void returnsChapterSegmentsForReader() throws Exception {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var bookEntity = bookRepository.findById(book.bookId()).orElseThrow();
        bookEntity.assignOwner(memberUser.getId());
        bookRepository.saveAndFlush(bookEntity);
        var chapter = chapterRepository.findByBookIdOrderByChapterOrderAsc(book.bookId()).getFirst();

        mockMvc.perform(get("/api/books/" + book.bookId() + "/chapters/" + chapter.getId() + "/segments")
                        .with(memberUser())
                        .param("mode", "bilingual"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.chapterId").value(chapter.getId()))
                .andExpect(jsonPath("$.segments[0].sourceText").exists())
                .andExpect(jsonPath("$.segments[0].translationStatus").exists());
    }

    private RequestPostProcessor memberUser() {
        return member(memberUser.getId(), memberUser.getUsername());
    }
}
