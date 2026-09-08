import { index, integer, real, sqliteTable, text, uniqueIndex } from 'drizzle-orm/sqlite-core';

const timestamps = {
  createdAt: integer('created_at', { mode: 'timestamp_ms' }).notNull(),
  updatedAt: integer('updated_at', { mode: 'timestamp_ms' }).notNull(),
};

export const workspaces = sqliteTable('workspaces', {
  id: text('id').primaryKey(), ownerUserId: text('owner_user_id').notNull(), name: text('name').notNull(), timezone: text('timezone').notNull().default('Asia/Shanghai'), ...timestamps,
}, (table) => [uniqueIndex('idx_workspaces_owner').on(table.ownerUserId)]);

export const dataSources = sqliteTable('data_sources', {
  id: text('id').primaryKey(), name: text('name').notNull(), sourceType: text('source_type').notNull(), licenseStatus: text('license_status').notNull(), licenseExpiresAt: integer('license_expires_at', { mode: 'timestamp_ms' }), retentionPolicy: text('retention_policy'), healthStatus: text('health_status').notNull().default('unconfigured'), ...timestamps,
});

export const competitions = sqliteTable('competitions', {
  id: text('id').primaryKey(), name: text('name').notNull(), countryCode: text('country_code'), competitionType: text('competition_type').notNull(), ...timestamps,
});

export const seasons = sqliteTable('seasons', {
  id: text('id').primaryKey(), competitionId: text('competition_id').notNull().references(() => competitions.id), name: text('name').notNull(), startsAt: integer('starts_at', { mode: 'timestamp_ms' }).notNull(), endsAt: integer('ends_at', { mode: 'timestamp_ms' }).notNull(), ...timestamps,
}, (table) => [uniqueIndex('idx_seasons_competition_name').on(table.competitionId, table.name)]);

export const teams = sqliteTable('teams', {
  id: text('id').primaryKey(), name: text('name').notNull(), shortName: text('short_name'), countryCode: text('country_code'), active: integer('active', { mode: 'boolean' }).notNull().default(true), ...timestamps,
});

export const externalMappings = sqliteTable('external_mappings', {
  id: text('id').primaryKey(), sourceId: text('source_id').notNull().references(() => dataSources.id), entityType: text('entity_type').notNull(), entityId: text('entity_id').notNull(), externalId: text('external_id').notNull(), confidence: real('confidence').notNull().default(1), reviewStatus: text('review_status').notNull().default('approved'), ...timestamps,
}, (table) => [uniqueIndex('idx_external_mapping_identity').on(table.sourceId, table.entityType, table.externalId), index('idx_external_mapping_entity').on(table.entityType, table.entityId)]);

export const matches = sqliteTable('matches', {
  id: text('id').primaryKey(), seasonId: text('season_id').notNull().references(() => seasons.id), homeTeamId: text('home_team_id').notNull().references(() => teams.id), awayTeamId: text('away_team_id').notNull().references(() => teams.id), scheduledAt: integer('scheduled_at', { mode: 'timestamp_ms' }).notNull(), status: text('status').notNull(), roundName: text('round_name'), dataQualityGrade: text('data_quality_grade').notNull().default('D'), ...timestamps,
}, (table) => [index('idx_matches_schedule_status').on(table.scheduledAt, table.status), index('idx_matches_season').on(table.seasonId)]);

export const matchResults = sqliteTable('match_results', {
  id: text('id').primaryKey(), matchId: text('match_id').notNull().references(() => matches.id), scope: text('scope').notNull().default('regular_time'), homeScore: integer('home_score').notNull(), awayScore: integer('away_score').notNull(), confirmationStatus: text('confirmation_status').notNull(), sourceCount: integer('source_count').notNull().default(1), confirmedAt: integer('confirmed_at', { mode: 'timestamp_ms' }), ...timestamps,
}, (table) => [uniqueIndex('idx_match_results_scope').on(table.matchId, table.scope)]);

export const oddsSnapshots = sqliteTable('odds_snapshots', {
  id: text('id').primaryKey(), matchId: text('match_id').notNull().references(() => matches.id), sourceId: text('source_id').notNull().references(() => dataSources.id), bookmaker: text('bookmaker').notNull(), marketType: text('market_type').notNull(), marketScope: text('market_scope').notNull().default('regular_time'), selection: text('selection').notNull(), lineValue: real('line_value'), decimalOdds: real('decimal_odds').notNull(), marketStatus: text('market_status').notNull(), sourcePublishedAt: integer('source_published_at', { mode: 'timestamp_ms' }), firstCollectedAt: integer('first_collected_at', { mode: 'timestamp_ms' }).notNull(), rawPayloadRef: text('raw_payload_ref'), ...timestamps,
}, (table) => [index('idx_odds_match_time').on(table.matchId, table.firstCollectedAt), uniqueIndex('idx_odds_snapshot_identity').on(table.sourceId, table.matchId, table.bookmaker, table.marketType, table.selection, table.firstCollectedAt)]);

export const featureSnapshots = sqliteTable('feature_snapshots', {
  id: text('id').primaryKey(), matchId: text('match_id').notNull().references(() => matches.id), featureSetVersion: text('feature_set_version').notNull(), cutoffAt: integer('cutoff_at', { mode: 'timestamp_ms' }).notNull(), maxInputAvailableAt: integer('max_input_available_at', { mode: 'timestamp_ms' }).notNull(), qualityGrade: text('quality_grade').notNull(), contentHash: text('content_hash').notNull(), payloadRef: text('payload_ref').notNull(), ...timestamps,
}, (table) => [uniqueIndex('idx_feature_snapshot_identity').on(table.matchId, table.featureSetVersion, table.cutoffAt)]);

export const modelVersions = sqliteTable('model_versions', {
  id: text('id').primaryKey(), modelName: text('model_name').notNull(), version: text('version').notNull(), modelType: text('model_type').notNull(), status: text('status').notNull(), artifactRef: text('artifact_ref'), trainedThrough: integer('trained_through', { mode: 'timestamp_ms' }), approvedAt: integer('approved_at', { mode: 'timestamp_ms' }), ...timestamps,
}, (table) => [uniqueIndex('idx_model_name_version').on(table.modelName, table.version)]);

export const modelPredictions = sqliteTable('model_predictions', {
  id: text('id').primaryKey(), matchId: text('match_id').notNull().references(() => matches.id), featureSnapshotId: text('feature_snapshot_id').notNull().references(() => featureSnapshots.id), modelVersionId: text('model_version_id').notNull().references(() => modelVersions.id), target: text('target').notNull(), probabilitiesJson: text('probabilities_json').notNull(), calibrated: integer('calibrated', { mode: 'boolean' }).notNull().default(false), producedAt: integer('produced_at', { mode: 'timestamp_ms' }).notNull(), ...timestamps,
}, (table) => [uniqueIndex('idx_model_prediction_identity').on(table.matchId, table.featureSnapshotId, table.modelVersionId, table.target)]);

export const forecastFreezes = sqliteTable('forecast_freezes', {
  id: text('id').primaryKey(), workspaceId: text('workspace_id').notNull().references(() => workspaces.id), matchId: text('match_id').notNull().references(() => matches.id), target: text('target').notNull(), fusionVersion: text('fusion_version').notNull(), probabilitiesJson: text('probabilities_json').notNull(), confidence: real('confidence').notNull(), riskLevel: text('risk_level').notNull(), dataCutoffAt: integer('data_cutoff_at', { mode: 'timestamp_ms' }).notNull(), frozenAt: integer('frozen_at', { mode: 'timestamp_ms' }).notNull(), supersedesId: text('supersedes_id'), correctionReason: text('correction_reason'), ...timestamps,
}, (table) => [uniqueIndex('idx_forecast_freeze_identity').on(table.workspaceId, table.matchId, table.target, table.frozenAt), index('idx_forecast_match').on(table.matchId)]);

export const userJudgments = sqliteTable('user_judgments', {
  id: text('id').primaryKey(), workspaceId: text('workspace_id').notNull().references(() => workspaces.id), matchId: text('match_id').notNull().references(() => matches.id), userId: text('user_id').notNull(), selection: text('selection').notNull(), confidence: integer('confidence').notNull(), reasonTagsJson: text('reason_tags_json').notNull().default('[]'), note: text('note'), isPostMatchNote: integer('is_post_match_note', { mode: 'boolean' }).notNull().default(false), ...timestamps,
}, (table) => [index('idx_judgments_workspace_match').on(table.workspaceId, table.matchId)]);

export const jobs = sqliteTable('jobs', {
  id: text('id').primaryKey(), jobType: text('job_type').notNull(), idempotencyKey: text('idempotency_key').notNull(), matchId: text('match_id').references(() => matches.id), status: text('status').notNull(), priority: integer('priority').notNull().default(100), scheduledAt: integer('scheduled_at', { mode: 'timestamp_ms' }).notNull(), startedAt: integer('started_at', { mode: 'timestamp_ms' }), finishedAt: integer('finished_at', { mode: 'timestamp_ms' }), attempts: integer('attempts').notNull().default(0), lastErrorCode: text('last_error_code'), traceId: text('trace_id'), ...timestamps,
}, (table) => [uniqueIndex('idx_jobs_idempotency').on(table.idempotencyKey), index('idx_jobs_status_schedule').on(table.status, table.scheduledAt)]);
