package com.fanbook.book.infrastructure;

import com.fanbook.book.domain.BookEntity;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface BookRepository extends JpaRepository<BookEntity, Long> {
    List<BookEntity> findByOwnerUserIdOrderByIdDesc(Long ownerUserId);
}
