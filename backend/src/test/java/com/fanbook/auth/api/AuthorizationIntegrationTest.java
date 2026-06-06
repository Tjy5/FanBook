package com.fanbook.auth.api;

import static com.fanbook.testsupport.SecurityMockMvcSupport.csrfToken;
import static com.fanbook.testsupport.SecurityMockMvcSupport.member;
import static com.fanbook.testsupport.SecurityMockMvcSupport.viewer;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fanbook.auth.domain.UserEntity;
import com.fanbook.auth.domain.UserRole;
import com.fanbook.auth.infrastructure.UserRepository;
import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.testsupport.MinimalEpubFactory;
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
class AuthorizationIntegrationTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:authorization;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/authorization-storage");
    }

    @Autowired
    MockMvc mockMvc;

    @Autowired
    UserRepository userRepository;

    @Autowired
    BookRepository bookRepository;

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
    void apiRequiresAuthentication() throws Exception {
        mockMvc.perform(get("/api/books"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("unauthenticated"));
    }

    @Test
    void viewerCanReadButCannotUpload() throws Exception {
        mockMvc.perform(get("/api/books").with(viewer()))
                .andExpect(status().isOk());

        MockMultipartFile file = new MockMultipartFile("file", "demo.epub", "application/epub+zip", MinimalEpubFactory.create());
        mockMvc.perform(multipart("/api/books").file(file).param("sourceLanguage", "en").with(viewer()).with(csrfToken()))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("forbidden"));
    }

    @Test
    void memberCanUploadWithCsrf() throws Exception {
        MockMultipartFile file = new MockMultipartFile("file", "demo.epub", "application/epub+zip", MinimalEpubFactory.create());

        mockMvc.perform(multipart("/api/books").file(file).param("sourceLanguage", "en").with(memberUser()).with(csrfToken()))
                .andExpect(status().isCreated());
    }

    @Test
    void viewerCannotGenerateExports() throws Exception {
        mockMvc.perform(post("/api/books/1/exports/zh").with(viewer()).with(csrfToken()))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("forbidden"));
    }

    private RequestPostProcessor memberUser() {
        return member(memberUser.getId(), memberUser.getUsername());
    }
}
