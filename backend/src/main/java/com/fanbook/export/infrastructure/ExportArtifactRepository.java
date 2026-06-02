package com.fanbook.export.infrastructure;

import com.fanbook.export.domain.ExportArtifactEntity;
import com.fanbook.export.domain.ExportArtifactKind;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ExportArtifactRepository extends JpaRepository<ExportArtifactEntity, Long> {
    Optional<ExportArtifactEntity> findFirstByBook_IdAndKindOrderByCreatedAtDescIdDesc(Long bookId, ExportArtifactKind kind);
}
