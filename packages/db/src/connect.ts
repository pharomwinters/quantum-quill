import { Client } from 'pg';

export function databaseUrl(): string {
  const url = process.env['DATABASE_URL'];
  if (url === undefined || url === '') {
    throw new Error('DATABASE_URL is not set. Copy .env.example to .env, or export it.');
  }
  return url;
}

/** A connected client. The caller ends it. */
export async function connect(url = databaseUrl()): Promise<Client> {
  const client = new Client({ connectionString: url });
  await client.connect();
  return client;
}

/** The same server, a different database — for creating and dropping scratch databases. */
export function withDatabase(url: string, database: string): string {
  const parsed = new URL(url);
  parsed.pathname = `/${database}`;
  return parsed.toString();
}
