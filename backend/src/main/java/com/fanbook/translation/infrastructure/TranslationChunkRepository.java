package com.fanbook.translation.infrastructure;

import com.fanbook.translation.domain.TranslationChunkEntity;
import com.fanbook.translation.domain.TranslationChunkStatus;
import java.util.Collection;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TranslationChunkRepository extends JpaRepository<TranslationChunkEntity, Long> {
    List<TranslationChunkEntity> findByJobIdOrderByChunkOrderAsc(Long jobId);

    List<TranslationChunkEntity> findByJobIdAndStatusInOrderByChunkOrderAsc(Long jobId, Collection<TranslationChunkStatus> statuses);
}
