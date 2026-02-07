SELECT (p.vehicle_durability * (1.0 + (COALESCE(p.feature_bullet, 0) / 100.0))  / (1 - (COALESCE(p.feature_passthru, 0)) / 100.0) /  p.powerscore) AS powerscore_specific_durability, p.* FROM parts AS p
WHERE p.vehicle_durability >= 30
ORDER BY (p.vehicle_durability * (1.0 + (COALESCE(p.feature_bullet, 0) / 100.0))  / (1 - (COALESCE(p.feature_passthru, 0)) / 100.0) /  p.powerscore) DESC,  p.name
