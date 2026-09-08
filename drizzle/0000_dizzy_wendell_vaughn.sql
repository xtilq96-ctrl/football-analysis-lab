CREATE TABLE `competitions` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`country_code` text,
	`competition_type` text NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `data_sources` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`source_type` text NOT NULL,
	`license_status` text NOT NULL,
	`license_expires_at` integer,
	`retention_policy` text,
	`health_status` text DEFAULT 'unconfigured' NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `external_mappings` (
	`id` text PRIMARY KEY NOT NULL,
	`source_id` text NOT NULL,
	`entity_type` text NOT NULL,
	`entity_id` text NOT NULL,
	`external_id` text NOT NULL,
	`confidence` real DEFAULT 1 NOT NULL,
	`review_status` text DEFAULT 'approved' NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL,
	FOREIGN KEY (`source_id`) REFERENCES `data_sources`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_external_mapping_identity` ON `external_mappings` (`source_id`,`entity_type`,`external_id`);--> statement-breakpoint
CREATE INDEX `idx_external_mapping_entity` ON `external_mappings` (`entity_type`,`entity_id`);--> statement-breakpoint
CREATE TABLE `feature_snapshots` (
	`id` text PRIMARY KEY NOT NULL,
	`match_id` text NOT NULL,
	`feature_set_version` text NOT NULL,
	`cutoff_at` integer NOT NULL,
	`max_input_available_at` integer NOT NULL,
	`quality_grade` text NOT NULL,
	`content_hash` text NOT NULL,
	`payload_ref` text NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL,
	FOREIGN KEY (`match_id`) REFERENCES `matches`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_feature_snapshot_identity` ON `feature_snapshots` (`match_id`,`feature_set_version`,`cutoff_at`);--> statement-breakpoint
CREATE TABLE `forecast_freezes` (
	`id` text PRIMARY KEY NOT NULL,
	`workspace_id` text NOT NULL,
	`match_id` text NOT NULL,
	`target` text NOT NULL,
	`fusion_version` text NOT NULL,
	`probabilities_json` text NOT NULL,
	`confidence` real NOT NULL,
	`risk_level` text NOT NULL,
	`data_cutoff_at` integer NOT NULL,
	`frozen_at` integer NOT NULL,
	`supersedes_id` text,
	`correction_reason` text,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL,
	FOREIGN KEY (`workspace_id`) REFERENCES `workspaces`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`match_id`) REFERENCES `matches`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_forecast_freeze_identity` ON `forecast_freezes` (`workspace_id`,`match_id`,`target`,`frozen_at`);--> statement-breakpoint
CREATE INDEX `idx_forecast_match` ON `forecast_freezes` (`match_id`);--> statement-breakpoint
CREATE TABLE `jobs` (
	`id` text PRIMARY KEY NOT NULL,
	`job_type` text NOT NULL,
	`idempotency_key` text NOT NULL,
	`match_id` text,
	`status` text NOT NULL,
	`priority` integer DEFAULT 100 NOT NULL,
	`scheduled_at` integer NOT NULL,
	`started_at` integer,
	`finished_at` integer,
	`attempts` integer DEFAULT 0 NOT NULL,
	`last_error_code` text,
	`trace_id` text,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL,
	FOREIGN KEY (`match_id`) REFERENCES `matches`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_jobs_idempotency` ON `jobs` (`idempotency_key`);--> statement-breakpoint
CREATE INDEX `idx_jobs_status_schedule` ON `jobs` (`status`,`scheduled_at`);--> statement-breakpoint
CREATE TABLE `match_results` (
	`id` text PRIMARY KEY NOT NULL,
	`match_id` text NOT NULL,
	`scope` text DEFAULT 'regular_time' NOT NULL,
	`home_score` integer NOT NULL,
	`away_score` integer NOT NULL,
	`confirmation_status` text NOT NULL,
	`source_count` integer DEFAULT 1 NOT NULL,
	`confirmed_at` integer,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL,
	FOREIGN KEY (`match_id`) REFERENCES `matches`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_match_results_scope` ON `match_results` (`match_id`,`scope`);--> statement-breakpoint
CREATE TABLE `matches` (
	`id` text PRIMARY KEY NOT NULL,
	`season_id` text NOT NULL,
	`home_team_id` text NOT NULL,
	`away_team_id` text NOT NULL,
	`scheduled_at` integer NOT NULL,
	`status` text NOT NULL,
	`round_name` text,
	`data_quality_grade` text DEFAULT 'D' NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL,
	FOREIGN KEY (`season_id`) REFERENCES `seasons`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`home_team_id`) REFERENCES `teams`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`away_team_id`) REFERENCES `teams`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `idx_matches_schedule_status` ON `matches` (`scheduled_at`,`status`);--> statement-breakpoint
CREATE INDEX `idx_matches_season` ON `matches` (`season_id`);--> statement-breakpoint
CREATE TABLE `model_predictions` (
	`id` text PRIMARY KEY NOT NULL,
	`match_id` text NOT NULL,
	`feature_snapshot_id` text NOT NULL,
	`model_version_id` text NOT NULL,
	`target` text NOT NULL,
	`probabilities_json` text NOT NULL,
	`calibrated` integer DEFAULT false NOT NULL,
	`produced_at` integer NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL,
	FOREIGN KEY (`match_id`) REFERENCES `matches`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`feature_snapshot_id`) REFERENCES `feature_snapshots`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`model_version_id`) REFERENCES `model_versions`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_model_prediction_identity` ON `model_predictions` (`match_id`,`feature_snapshot_id`,`model_version_id`,`target`);--> statement-breakpoint
CREATE TABLE `model_versions` (
	`id` text PRIMARY KEY NOT NULL,
	`model_name` text NOT NULL,
	`version` text NOT NULL,
	`model_type` text NOT NULL,
	`status` text NOT NULL,
	`artifact_ref` text,
	`trained_through` integer,
	`approved_at` integer,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_model_name_version` ON `model_versions` (`model_name`,`version`);--> statement-breakpoint
CREATE TABLE `odds_snapshots` (
	`id` text PRIMARY KEY NOT NULL,
	`match_id` text NOT NULL,
	`source_id` text NOT NULL,
	`bookmaker` text NOT NULL,
	`market_type` text NOT NULL,
	`market_scope` text DEFAULT 'regular_time' NOT NULL,
	`selection` text NOT NULL,
	`line_value` real,
	`decimal_odds` real NOT NULL,
	`market_status` text NOT NULL,
	`source_published_at` integer,
	`first_collected_at` integer NOT NULL,
	`raw_payload_ref` text,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL,
	FOREIGN KEY (`match_id`) REFERENCES `matches`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`source_id`) REFERENCES `data_sources`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `idx_odds_match_time` ON `odds_snapshots` (`match_id`,`first_collected_at`);--> statement-breakpoint
CREATE UNIQUE INDEX `idx_odds_snapshot_identity` ON `odds_snapshots` (`source_id`,`match_id`,`bookmaker`,`market_type`,`selection`,`first_collected_at`);--> statement-breakpoint
CREATE TABLE `seasons` (
	`id` text PRIMARY KEY NOT NULL,
	`competition_id` text NOT NULL,
	`name` text NOT NULL,
	`starts_at` integer NOT NULL,
	`ends_at` integer NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL,
	FOREIGN KEY (`competition_id`) REFERENCES `competitions`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_seasons_competition_name` ON `seasons` (`competition_id`,`name`);--> statement-breakpoint
CREATE TABLE `teams` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`short_name` text,
	`country_code` text,
	`active` integer DEFAULT true NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `user_judgments` (
	`id` text PRIMARY KEY NOT NULL,
	`workspace_id` text NOT NULL,
	`match_id` text NOT NULL,
	`user_id` text NOT NULL,
	`selection` text NOT NULL,
	`confidence` integer NOT NULL,
	`reason_tags_json` text DEFAULT '[]' NOT NULL,
	`note` text,
	`is_post_match_note` integer DEFAULT false NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL,
	FOREIGN KEY (`workspace_id`) REFERENCES `workspaces`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`match_id`) REFERENCES `matches`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `idx_judgments_workspace_match` ON `user_judgments` (`workspace_id`,`match_id`);--> statement-breakpoint
CREATE TABLE `workspaces` (
	`id` text PRIMARY KEY NOT NULL,
	`owner_user_id` text NOT NULL,
	`name` text NOT NULL,
	`timezone` text DEFAULT 'Asia/Shanghai' NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_workspaces_owner` ON `workspaces` (`owner_user_id`);