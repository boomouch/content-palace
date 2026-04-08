-- Migrate 'good' and 'fine' feelings to 'average'
UPDATE items SET feeling = 'average' WHERE feeling IN ('good', 'fine');

-- Update the check constraint
ALTER TABLE items DROP CONSTRAINT IF EXISTS items_feeling_check;
ALTER TABLE items ADD CONSTRAINT items_feeling_check
  CHECK (feeling IN ('essential', 'loved', 'average', 'not_for_me', 'regret'));
