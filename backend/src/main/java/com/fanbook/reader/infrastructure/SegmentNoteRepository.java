package com.fanbook.reader.infrastructure;

import com.fanbook.reader.domain.SegmentNoteEntity;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface SegmentNoteRepository extends JpaRepository<SegmentNoteEntity, Long> {
    List<SegmentNoteEntity> findBySegmentIdOrderByCreatedAtAscIdAsc(Long segmentId);

    long countBySegmentId(Long segmentId);

    @Query("""
            select note from SegmentNoteEntity note
            join fetch note.segment segment
            join fetch segment.chapter chapter
            where note.book.id = :bookId
            order by chapter.chapterOrder asc, segment.segmentOrder asc, note.createdAt asc, note.id asc
            """)
    List<SegmentNoteEntity> findByBookIdForExport(Long bookId);
}
