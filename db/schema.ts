import { sqliteTable, text, integer, uniqueIndex, index } from 'drizzle-orm/sqlite-core';
export const entries=sqliteTable('entries',{
 sequence:integer('sequence').primaryKey({autoIncrement:true}),
 userId:text('user_id').notNull(),recordId:text('record_id').notNull(),
 kind:text('kind').notNull(),payload:text('payload').notNull(),createdAt:text('created_at').notNull(),
},t=>[uniqueIndex('entries_user_record').on(t.userId,t.recordId),index('entries_user_sequence').on(t.userId,t.sequence)]);
