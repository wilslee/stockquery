drop table if exists "user";
create table "user" (
  id serial primary key,
  username varchar(64) not null unique,
  password varchar(128) not null
);

drop table if exists history;
create table history (
  id serial primary key,
  user_id integer not null,
  stock_code varchar(64) not null,
  result varchar(256) not null,
  query_time timestamp
);

drop table if exists wxuser_history;
create table wxuser_history (
  id serial primary key,
  openid varchar(128) not null,
  stock_code varchar(64) not null,
  result varchar(256) not null,
  query_time timestamp
);
