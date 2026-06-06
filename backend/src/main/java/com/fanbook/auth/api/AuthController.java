package com.fanbook.auth.api;

import com.fanbook.auth.application.CurrentUser;
import com.fanbook.auth.application.CurrentUserProvider;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.Comparator;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.logout.SecurityContextLogoutHandler;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AuthController {

    private final AuthenticationManager authenticationManager;
    private final CurrentUserProvider currentUserProvider;
    private final SecurityContextRepository securityContextRepository;

    public AuthController(
            AuthenticationManager authenticationManager,
            CurrentUserProvider currentUserProvider,
            SecurityContextRepository securityContextRepository
    ) {
        this.authenticationManager = authenticationManager;
        this.currentUserProvider = currentUserProvider;
        this.securityContextRepository = securityContextRepository;
    }

    @GetMapping("/api/auth/csrf")
    public CsrfTokenResponse csrf(CsrfToken csrfToken) {
        return new CsrfTokenResponse(csrfToken.getToken(), csrfToken.getHeaderName(), csrfToken.getParameterName());
    }

    @PostMapping("/api/auth/login")
    public UserResponse login(
            @RequestBody LoginRequest request,
            CsrfToken csrfToken,
            HttpServletRequest servletRequest,
            HttpServletResponse servletResponse
    ) {
        Authentication authentication = authenticationManager.authenticate(new UsernamePasswordAuthenticationToken(
                request == null ? null : request.username(),
                request == null ? null : request.password()
        ));
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(authentication);
        SecurityContextHolder.setContext(context);
        securityContextRepository.saveContext(context, servletRequest, servletResponse);
        return toResponse(currentUserProvider.requireCurrentUser(), csrfToken);
    }

    @PostMapping("/api/auth/logout")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void logout(HttpServletRequest request, HttpServletResponse response) {
        new SecurityContextLogoutHandler().logout(request, response, SecurityContextHolder.getContext().getAuthentication());
    }

    @GetMapping("/api/auth/me")
    public UserResponse me(CsrfToken csrfToken) {
        return toResponse(currentUserProvider.requireCurrentUser(), csrfToken);
    }

    private static UserResponse toResponse(CurrentUser user, CsrfToken csrfToken) {
        return new UserResponse(
                user.id(),
                user.username(),
                user.email(),
                user.roles().stream().map(Enum::name).sorted(Comparator.naturalOrder()).toList(),
                csrfToken.getToken(),
                csrfToken.getHeaderName()
        );
    }
}
