package com.fanbook.auth.infrastructure;

import com.fanbook.auth.domain.UserEntity;
import com.fanbook.auth.domain.UserRole;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface UserRepository extends JpaRepository<UserEntity, Long> {

    Optional<UserEntity> findByUsername(String username);

    boolean existsByUsername(String username);

    boolean existsByEmail(String email);

    @Query("select count(u) > 0 from UserEntity u join u.roles role where role = :role")
    boolean existsByRole(UserRole role);

    @Query("select count(u) from UserEntity u join u.roles role where role = :role")
    long countByRole(UserRole role);
}
