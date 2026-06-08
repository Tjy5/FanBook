package com.fanbook.translation.infrastructure;

import com.fanbook.translation.domain.TranslationRuleSnapshotEntity;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TranslationRuleSnapshotRepository extends JpaRepository<TranslationRuleSnapshotEntity, Long> {
    Optional<TranslationRuleSnapshotEntity> findFirstByBookIdAndSnapshotHashOrderByIdDesc(Long bookId, String snapshotHash);
}
