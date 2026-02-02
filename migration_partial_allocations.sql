-- Migration Script: Add Partial Allocations Support
-- This script adds the allocated_amount column and modifies the unique constraint
-- to allow multiple allocations per budget line item.

-- Step 1: Add allocated_amount column
ALTER TABLE budget_state 
ADD COLUMN allocated_amount DECIMAL(15, 2) NULL AFTER amount;

-- Step 2: Update existing rows to set allocated_amount = amount for rows with status_category
-- Temporarily disable safe update mode for this operation
SET SQL_SAFE_UPDATES = 0;

UPDATE budget_state 
SET allocated_amount = amount 
WHERE status_category IS NOT NULL AND status_category != '';

SET SQL_SAFE_UPDATES = 1;

-- Step 3: Drop the old unique constraint (unique_budget_line)
-- First, check if the index exists and drop it safely
DROP PROCEDURE IF EXISTS drop_index_if_exists;

DELIMITER $$

CREATE PROCEDURE drop_index_if_exists()
BEGIN
    DECLARE index_exists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO index_exists
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'budget_state'
      AND INDEX_NAME = 'unique_budget_line';
    
    IF index_exists > 0 THEN
        ALTER TABLE budget_state DROP INDEX unique_budget_line;
    END IF;
END$$

DELIMITER ;

CALL drop_index_if_exists();
DROP PROCEDURE IF EXISTS drop_index_if_exists;

-- Step 4: Create new unique constraint to allow multiple allocations per line item
-- Unique constraint: (file_name, category, subcategory, status_category)
-- Using column prefixes to avoid "key too long" error
ALTER TABLE budget_state
ADD UNIQUE KEY unique_budget_allocation (
    file_name(100),
    category(100),
    subcategory(100),
    status_category(50)
);
