SELECT (p.vehicle_durability * (1.0 + (COALESCE(p.feature_bullet, 0) / 100.0))  / (1 - (COALESCE(p.feature_passthru, 0)) / 100.0) /  p.mass) as weight_specific_durability, p.* FROM parts AS p
WHERE COALESCE(p.vehicle_durability,0) >= 30
ORDER BY (p.vehicle_durability * (1.0 + (COALESCE(p.feature_bullet, 0) / 100.0))  / (1 - (COALESCE(p.feature_passthru, 0)) / 100.0) /  p.mass) DESC,  p.name