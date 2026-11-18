-- Seats belong to a show and are free until a reservation holds them.
create table if not exists seats (
    show_id text not null,
    seat    text not null,
    status  text not null default 'free',
    primary key (show_id, seat)
);

-- A reservation is keyed by an id derived from its idempotency key, so a retry
-- finds the reservation that already exists instead of making another one.
create table if not exists reservations (
    reservation_id text primary key,
    show_id        text not null,
    seats          text[] not null,
    status         text not null,
    expires_at     timestamptz not null,
    created_at     timestamptz not null default now()
);
