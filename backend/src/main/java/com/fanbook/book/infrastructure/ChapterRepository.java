package com.fanbook.book.infrastructure;

import com.fanbook.book.domain.ChapterEntity;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ChapterRepository extends JpaRepository<ChapterEntity, Long> {
    List<ChapterEntity> findByBookIdOrderByChapterOrderAsc(Long bookId);
}
