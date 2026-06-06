package com.fanbook.reader.api;

import static com.fanbook.testsupport.SecurityMockMvcSupport.csrfToken;
import static com.fanbook.testsupport.SecurityMockMvcSupport.admin;
import static com.fanbook.testsupport.SecurityMockMvcSupport.member;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.auth.domain.UserEntity;
import com.fanbook.auth.domain.UserRole;
import com.fanbook.auth.infrastructure.UserRepository;
import com.fanbook.book.application.BookApplicationService;
import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.testsupport.MinimalEpubFactory;
import java.util.Set;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@SpringBootTest
@AutoConfigureMockMvc
class SegmentNoteControllerIntegrationTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:segment_note_controller;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/segment-note-controller-storage");
    }

    @Autowired
    MockMvc mockMvc;

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    SegmentRepository segmentRepository;

    @Autowired
    BookRepository bookRepository;

    @Autowired
    UserRepository userRepository;

    private UserEntity memberUser;
    private UserEntity otherMember;

    private final ObjectMapper objectMapper = JsonMapper.builder().build();

    @BeforeEach
    void seedUsers() {
        bookRepository.deleteAll();
        userRepository.deleteAll();
        memberUser = userRepository.save(new UserEntity(
                "member",
                "member@example.test",
                "{noop}password",
                Set.of(UserRole.MEMBER)
        ));
        otherMember = userRepository.save(new UserEntity(
                "other-member",
                "other-member@example.test",
                "{noop}password",
                Set.of(UserRole.MEMBER)
        ));
    }

    @Test
    void createsListsUpdatesDeletesAndExportsNotes() throws Exception {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        assignOwner(book.bookId(), memberUser);
        var segment = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId()).getFirst();

        String created = mockMvc.perform(post("/api/segments/" + segment.getId() + "/notes")
                        .with(memberUser())
                        .with(csrfToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"content\":\"classic opening\",\"highlightColor\":\"yellow\"}"))
                .andExpect(status().isCreated())
                .andExpect(content().string(containsString("\"createdBy\":\"member\"")))
                .andReturn().getResponse().getContentAsString();

        Long noteId = objectMapper.readTree(created).get("noteId").asLong();
        mockMvc.perform(get("/api/segments/" + segment.getId() + "/notes").with(memberUser()))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("classic opening")));
        mockMvc.perform(put("/api/notes/" + noteId)
                        .with(memberUser())
                        .with(csrfToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"content\":\"updated note\",\"highlightColor\":\"green\"}"))
                .andExpect(status().isOk());
        mockMvc.perform(get("/api/books/" + book.bookId() + "/notes/export").with(memberUser()))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("updated note")));
        mockMvc.perform(delete("/api/notes/" + noteId).with(memberUser()).with(csrfToken()))
                .andExpect(status().isNoContent());
    }

    @Test
    void onlyNoteOwnerOrAdminCanMutateNotes() throws Exception {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        assignOwner(book.bookId(), memberUser);
        var segment = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId()).getFirst();

        String created = mockMvc.perform(post("/api/segments/" + segment.getId() + "/notes")
                        .with(memberUser())
                        .with(csrfToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"content\":\"owned note\"}"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        Long noteId = objectMapper.readTree(created).get("noteId").asLong();

        mockMvc.perform(put("/api/notes/" + noteId)
                        .with(otherMember())
                        .with(csrfToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"content\":\"takeover\"}"))
                .andExpect(status().isForbidden());

        mockMvc.perform(delete("/api/notes/" + noteId).with(admin()).with(csrfToken()))
                .andExpect(status().isNoContent());
    }

    private void assignOwner(Long bookId, UserEntity user) {
        var book = bookRepository.findById(bookId).orElseThrow();
        book.assignOwner(user.getId());
        bookRepository.saveAndFlush(book);
    }

    private RequestPostProcessor memberUser() {
        return member(memberUser.getId(), memberUser.getUsername());
    }

    private RequestPostProcessor otherMember() {
        return member(otherMember.getId(), otherMember.getUsername());
    }
}
