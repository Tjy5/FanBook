package com.fanbook.reader.api;

import com.fanbook.reader.application.ReaderApplicationService;
import com.fanbook.reader.application.SegmentNoteService;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ReaderController {

    private final ReaderApplicationService service;
    private final SegmentNoteService noteService;

    public ReaderController(ReaderApplicationService service, SegmentNoteService noteService) {
        this.service = service;
        this.noteService = noteService;
    }

    @GetMapping("/api/books/{bookId}/reader/info")
    public ReaderInfoResponse info(@PathVariable Long bookId) {
        return service.info(bookId);
    }

    @GetMapping("/api/books/{bookId}/chapters")
    public ChapterListResponse chapters(@PathVariable Long bookId) {
        return service.chapters(bookId);
    }

    @GetMapping("/api/books/{bookId}/chapters/{chapterId}/segments")
    public ChapterSegmentResponse segments(
            @PathVariable Long bookId,
            @PathVariable Long chapterId,
            @RequestParam(defaultValue = "bilingual") String mode
    ) {
        return service.segments(bookId, chapterId, mode);
    }

    @PostMapping("/api/segments/{segmentId}/notes")
    @ResponseStatus(HttpStatus.CREATED)
    public SegmentNoteResponse createNote(
            @PathVariable Long segmentId,
            @RequestBody CreateNoteRequest request
    ) {
        return noteService.create(segmentId, request);
    }

    @GetMapping("/api/segments/{segmentId}/notes")
    public List<SegmentNoteResponse> notes(@PathVariable Long segmentId) {
        return noteService.notes(segmentId);
    }

    @PutMapping("/api/notes/{noteId}")
    public SegmentNoteResponse updateNote(
            @PathVariable Long noteId,
            @RequestBody UpdateNoteRequest request
    ) {
        return noteService.update(noteId, request);
    }

    @DeleteMapping("/api/notes/{noteId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteNote(@PathVariable Long noteId) {
        noteService.delete(noteId);
    }

    @GetMapping("/api/books/{bookId}/notes/export")
    public ResponseEntity<String> exportNotes(@PathVariable Long bookId) {
        return ResponseEntity.ok()
                .contentType(MediaType.valueOf("text/markdown"))
                .body(noteService.exportMarkdown(bookId));
    }
}
