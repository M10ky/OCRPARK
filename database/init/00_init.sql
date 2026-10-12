-- =========================================================================
-- SM-Park - Initialisation PostgreSQL
-- -------------------------------------------------------------------------
-- Exécuté automatiquement au premier démarrage du conteneur `database`
-- (répertoire /docker-entrypoint-initdb.d).
-- NE contient que la configuration de base : extensions + paramètres.
-- Le schéma métier (tables) est géré par les modèles SQLAlchemy du backend
-- (Phase 5) afin d'éviter tout conflit de source de vérité.
-- =========================================================================

-- --- Extensions utiles ---
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- --- Paramètres de la base courante ---
DO $$
BEGIN
    EXECUTE format(
        'ALTER DATABASE %I SET timezone TO %L',
        current_database(),
        'Indian/Antananarivo'
    );
    EXECUTE format(
        'ALTER DATABASE %I SET timezone TO %L',
        'template1',
        'Indian/Antananarivo'
    );
END $$;

-- --- Message de confirmation (visible dans les logs du conteneur) ---
DO $$
BEGIN
    RAISE NOTICE 'SM-Park : extensions et paramètres de base initialisés.';
END $$;
