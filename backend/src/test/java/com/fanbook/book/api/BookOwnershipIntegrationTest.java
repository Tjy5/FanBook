package com.fanbook.book.api;

import static com.fanbook.testsupport.SecurityMockMvcSupport.csrfToken;
import static com.fanbook.testsupport.SecurityMockMvcSupport.localUser;
import static com.fanbook.testsupport.SecurityMockMvcSupport.member;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.auth.domain.UserEntity;
import com.fanbook.auth.domain.UserRole;
import com.fanbook.auth.infrastructure.UserRepository;
import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.BookStatus;
import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.export.domain.ExportArtifactEntity;
import com.fanbook.export.domain.ExportArtifactKind;
import com.fanbook.export.domain.ExportArtifactStatus;
import com.fanbook.export.infrastructure.ExportArtifactRepository;
import com.fanbook.testsupport.MinimalEpubFactory;
import java.nio.charset.StandardCharsets;
import java.util.Set;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@SpringBootTest
@AutoConfigureMockMvc
class BookOwnershipIntegrationTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:book_ownership;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/book-ownership-storage");
    }

    @Autowired
    MockMvc mockMvc;

    @Autowired
    UserRepository userRepository;

    @Autowired
    BookRepository bookRepository;

    @Autowired
    SegmentRepository segmentRepository;

    @Autowired
    ExportArtifactRepository artifactRepository;

    private final ObjectMapper objectMapper = JsonMapper.builder().build();

    private UserEntity owner;
    private UserEntity otherMember;
    private UserEntity admin;

    @BeforeEach
    void seedUsers() {
        artifactRepository.deleteAll();
        segmentRepository.deleteAll();
        bookRepository.deleteAll();
        userRepository.deleteAll();
        owner = userRepository.save(new UserEntity("owner", "owner@example.test", "{noop}password", Set.of(UserRole.MEMBER)));
        otherMember = userRepository.save(new UserEntity("other", "other@example.test", "{noop}password", Set.of(UserRole.MEMBER)));
        admin = userRepository.save(new UserEntity("admin", "admin@example.test", "{noop}password", Set.of(UserRole.ADMIN)));
    }

    @Test
    void usersOnlyListTheirOwnBooks() throws Exception {
        Long ownerBookId = uploadBook(owner, "owner.epub");
        Long otherBookId = uploadBook(otherMember, "other.epub");

        mockMvc.perform(get("/api/books").with(user(owner)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status_counts.total").value(1))
                .andExpect(content().string(containsString("\"id\":" + ownerBookId)))
                .andExpect(content().string(not(containsString("\"id\":" + otherBookId))));

        mockMvc.perform(get("/api/books").with(adminUser()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status_counts.total").value(2));
    }

    @Test
    void nonOwnerCannotReadTranslateExportOrNotePrivateBook() throws Exception {
        Long bookId = uploadBook(owner, "private.epub");
        Long segmentId = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(bookId).getFirst().getId();

        mockMvc.perform(get("/api/books/" + bookId).with(user(otherMember)))
                .andExpect(status().isForbidden());
        mockMvc.perform(get("/api/books/" + bookId + "/chapters").with(user(otherMember)))
                .andExpect(status().isForbidden());
        mockMvc.perform(post("/api/books/" + bookId + "/translation-jobs")
                        .with(user(otherMember))
                        .with(csrfToken())
                        .contentType("application/json")
                        .content("{\"providerName\":\"mock\",\"modelName\":\"mock-translator\"}"))
                .andExpect(status().isForbidden());
        mockMvc.perform(post("/api/books/" + bookId + "/exports/zh").with(user(otherMember)).with(csrfToken()))
                .andExpect(status().isForbidden());
        mockMvc.perform(post("/api/segments/" + segmentId + "/notes")
                        .with(user(otherMember))
                        .with(csrfToken())
                        .contentType("application/json")
                        .content("{\"content\":\"take note\"}"))
                .andExpect(status().isForbidden());
    }

    @Test
    void nonOwnerCannotDownloadReadyArtifacts() throws Exception {
        Long bookId = uploadBook(owner, "ready.epub");
        var book = bookRepository.findById(bookId).orElseThrow();
        ExportArtifactEntity artifact = new ExportArtifactEntity(book, ExportArtifactKind.ZH_EPUB, ExportArtifactStatus.READY, "zh.epub");
        artifact.markReady("exports/" + bookId + "/zh.epub", 7L, "checksum");
        artifactRepository.saveAndFlush(artifact);

        mockMvc.perform(get("/api/books/" + bookId + "/exports/zh").with(user(otherMember)))
                .andExpect(status().isForbidden());
    }

    @Test
    void adminCanReadPrivateBookOwnedByAnotherUser() throws Exception {
        Long bookId = uploadBook(owner, "private.epub");

        mockMvc.perform(get("/api/books/" + bookId).with(adminUser()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.book.id").value(bookId));
    }

    @Test
    void legacySystemBooksAreAdminOnly() throws Exception {
        BookEntity systemBook = bookRepository.saveAndFlush(new BookEntity(
                "legacy.epub",
                "Legacy Book",
                "en",
                "books/legacy/source.epub",
                BookStatus.PARSED
        ));

        mockMvc.perform(get("/api/books").with(user(owner)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status_counts.total").value(0))
                .andExpect(content().string(not(containsString("\"id\":" + systemBook.getId()))));
        mockMvc.perform(get("/api/books/" + systemBook.getId()).with(user(owner)))
                .andExpect(status().isForbidden());

        mockMvc.perform(get("/api/books").with(adminUser()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status_counts.total").value(1))
                .andExpect(content().string(containsString("\"id\":" + systemBook.getId())));
        mockMvc.perform(get("/api/books/" + systemBook.getId()).with(adminUser()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.book.id").value(systemBook.getId()));
    }

    private Long uploadBook(UserEntity user, String filename) throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file",
                filename,
                "application/epub+zip",
                MinimalEpubFactory.create()
        );
        String body = mockMvc.perform(multipart("/api/books")
                        .file(file)
                        .param("sourceLanguage", "en")
                        .with(user(user))
                        .with(csrfToken()))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        return objectMapper.readTree(body).get("bookId").asLong();
    }

    private RequestPostProcessor user(UserEntity user) {
        return member(user.getId(), user.getUsername());
    }

    private RequestPostProcessor adminUser() {
        return localUser(admin.getId(), admin.getUsername(), UserRole.ADMIN);
    }
}
