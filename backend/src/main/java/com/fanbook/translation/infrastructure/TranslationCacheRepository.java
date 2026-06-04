package com.fanbook.translation.infrastructure;

import com.fanbook.translation.domain.TranslationCacheEntity;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TranslationCacheRepository extends JpaRepository<TranslationCacheEntity, Long> {
    Optional<TranslationCacheEntity> findByCacheKey(String cacheKey);
}
