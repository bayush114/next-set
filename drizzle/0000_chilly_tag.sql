CREATE TABLE `entries` (
	`sequence` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`user_id` text NOT NULL,
	`record_id` text NOT NULL,
	`kind` text NOT NULL,
	`payload` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `entries_user_record` ON `entries` (`user_id`,`record_id`);--> statement-breakpoint
CREATE INDEX `entries_user_sequence` ON `entries` (`user_id`,`sequence`);