package com.fanbook.book.infrastructure;

import com.fanbook.book.domain.SegmentEntity;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SegmentRepository extends JpaRepository<SegmentEntity, Long> {
    List<SegmentEntity> findByBookIdOrderByChapterIdAscSegmentOrderAsc(Long bookId);

    List<SegmentEntity> findByChapterIdOrderBySegmentOrderAsc(Long chapterId);
}
