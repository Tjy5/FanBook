package com.fanbook.auth.application;

import com.fanbook.auth.domain.UserEntity;
import com.fanbook.auth.domain.UserRole;
import java.util.Collection;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

public class LocalUserPrincipal implements UserDetails {

    private final Long id;
    private final String username;
    private final String email;
    private final String passwordHash;
    private final boolean enabled;
    private final Set<UserRole> roles;
    private final Collection<GrantedAuthority> authorities;

    public LocalUserPrincipal(UserEntity user) {
        this(
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                user.getPasswordHash(),
                user.isEnabled(),
                user.getRoles()
        );
    }

    public LocalUserPrincipal(
            Long id,
            String username,
            String email,
            String passwordHash,
            boolean enabled,
            Set<UserRole> roles
    ) {
        this.id = id;
        this.username = username;
        this.email = email;
        this.passwordHash = passwordHash;
        this.enabled = enabled;
        this.roles = Set.copyOf(roles);
        this.authorities = this.roles.stream()
                .map(role -> new SimpleGrantedAuthority("ROLE_" + role.name()))
                .collect(Collectors.toUnmodifiableSet());
    }

    public Long id() {
        return id;
    }

    public String email() {
        return email;
    }

    public Set<UserRole> roles() {
        return roles;
    }

    public CurrentUser toCurrentUser() {
        return new CurrentUser(id, username, email, roles);
    }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return authorities;
    }

    @Override
    public String getPassword() {
        return passwordHash;
    }

    @Override
    public String getUsername() {
        return username;
    }

    @Override
    public boolean isEnabled() {
        return enabled;
    }
}
