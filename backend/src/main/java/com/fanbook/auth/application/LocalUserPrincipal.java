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
        this.id = user.getId();
        this.username = user.getUsername();
        this.email = user.getEmail();
        this.passwordHash = user.getPasswordHash();
        this.enabled = user.isEnabled();
        this.roles = user.getRoles();
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
