CREATE TABLE IF NOT EXISTS providers_doctors (
  npi BIGINT PRIMARY KEY,
  first_name TEXT,
  last_name TEXT,
  middle_name TEXT,
  credential TEXT,
  sex CHAR(1),
  taxonomy_code TEXT,
  specialty_desc TEXT,
  is_sole_proprietor CHAR(1),
  addr_line1 TEXT,
  addr_line2 TEXT,
  city TEXT,
  state TEXT,
  zip TEXT,
  phone TEXT,
  fax TEXT,
  enumeration_date DATE,
  last_updated DATE,
  deactivation_date DATE
);

CREATE TABLE IF NOT EXISTS providers_dentists (LIKE providers_doctors INCLUDING ALL);
CREATE TABLE IF NOT EXISTS providers_pharmacists (LIKE providers_doctors INCLUDING ALL);
