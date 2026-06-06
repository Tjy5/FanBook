ALTER TABLE books
    ADD COLUMN owner_user_id BIGINT;

ALTER TABLE books
    ADD CONSTRAINT fk_books_owner_user
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
    ON DELETE SET NULL;

CREATE INDEX idx_books_owner_id ON books(owner_user_id, id);
