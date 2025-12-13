from typing import List, Tuple, Optional
from Levenshtein import distance as levenshtein_distance

class FuzzyMatcher:
    def __init__(self, max_distance: int = 2):
        self.max_distance = max_distance
    
    def normalize(self, text: str) -> str:
        return text.lower().replace(' ', '').replace('-', '').replace('_', '').replace("'", '')
    
    def distance(self, s1: str, s2: str) -> int:
        return levenshtein_distance(self.normalize(s1), self.normalize(s2))
    
    def is_match(self, query: str, target: str) -> bool:
        norm_query = self.normalize(query)
        norm_target = self.normalize(target)
        
        if norm_query == norm_target:
            return True
        
        if norm_query in norm_target or norm_target in norm_query:
            return True
        
        return self.distance(query, target) <= self.max_distance
    
    def find_matches(self, query: str, candidates: List[str], limit: int = 5) -> List[Tuple[str, int]]:
        norm_query = self.normalize(query)
        results = []
        
        for candidate in candidates:
            norm_candidate = self.normalize(candidate)
            
            if norm_query == norm_candidate:
                results.append((candidate, 0))
                continue
            
            if norm_query in norm_candidate:
                results.append((candidate, 1))
                continue
            
            dist = levenshtein_distance(norm_query, norm_candidate)
            if dist <= self.max_distance:
                results.append((candidate, dist))
        
        results.sort(key=lambda x: (x[1], len(x[0])))
        return results[:limit]
    
    def best_match(self, query: str, candidates: List[str]) -> Optional[Tuple[str, int]]:
        matches = self.find_matches(query, candidates, limit=1)
        return matches[0] if matches else None
    
    def suggest(self, query: str, candidates: List[str], limit: int = 3) -> List[str]:
        matches = self.find_matches(query, candidates, limit=limit)
        return [m[0] for m in matches]


fuzzy_matcher = FuzzyMatcher()
