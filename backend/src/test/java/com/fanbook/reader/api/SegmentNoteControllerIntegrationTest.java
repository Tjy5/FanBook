package com.fanbook.reader.api;

import static com.fanbook.testsupport.SecurityMockMvcSupport.csrfToken;
import static com.fanbook.testsupport.SecurityMockMvcSupport.admin;
import static com.fanbook.testsupport.SecurityMockMvcSupport.member;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.book.application.BookApplicationService;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.testsupport.MinimalEpubFactory;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

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

    private final ObjectMapper objectMapper = JsonMapper.builder().build();

    @Test
    void createsListsUpdatesDeletesAndExportsNotes() throws Exception {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var segment = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId()).getFirst();

        String created = mockMvc.perform(post("/api/segments/" + segment.getId() + "/notes")
                        .with(member())
                        .with(csrfToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"content\":\"classic opening\",\"highlightColor\":\"yellow\"}"))
                .andExpect(status().isCreated())
                .andExpect(content().string(containsString("\"createdBy\":\"member\"")))
                .andReturn().getResponse().getContentAsString();

        Long noteId = objectMapper.readTree(created).get("noteId").asLong();
        mockMvc.perform(get("/api/segments/" + segment.getId() + "/notes").with(member()))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("classic opening")));
        mockMvc.perform(put("/api/notes/" + noteId)
                        .with(member())
                        .with(csrfToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"content\":\"updated note\",\"highlightColor\":\"green\"}"))
                .andExpect(status().isOk());
        mockMvc.perform(get("/api/books/" + book.bookId() + "/notes/export").with(member()))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("updated note")));
        mockMvc.perform(delete("/api/notes/" + noteId).with(member()).with(csrfToken()))
                .andExpect(status().isNoContent());
    }

    @Test
    void onlyNoteOwnerOrAdminCanMutateNotes() throws Exception {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var segment = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId()).getFirst();

        String created = mockMvc.perform(post("/api/segments/" + segment.getId() + "/notes")
                        .with(member())
                        .with(csrfToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"content\":\"owned note\"}"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        Long noteId = objectMapper.readTree(created).get("noteId").asLong();

        mockMvc.perform(put("/api/notes/" + noteId)
                        .with(user("other-member").roles("MEMBER"))
                        .with(csrfToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"content\":\"takeover\"}"))
                .andExpect(status().isForbidden());

        mockMvc.perform(delete("/api/notes/" + noteId).with(admin()).with(csrfToken()))
                .andExpect(status().isNoContent());
    }
}
