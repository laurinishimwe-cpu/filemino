import hashlib, hmac, time
from uuid import UUID
from redis import Redis
from app.core.exceptions import RateLimitedError, TooManyActiveJobsError
class RateLimitService:
    def __init__(self,redis_client:Redis,salt:str)->None: self.redis=redis_client; self.salt=salt.encode()
    def subject_hash(self,value:str)->str: return hmac.new(self.salt,value.encode(),hashlib.sha256).hexdigest()
    def consume_job_request(self,subject:str,limit:int)->None:
        key=f"fluxfile:rate:jobs:{subject}:{int(time.time()//3600)}"; count=self.redis.incr(key)
        if count==1:self.redis.expire(key,3600)
        if count>limit:raise RateLimitedError()
    def claim_concurrent(self,subject:str,job_id:UUID,limit:int,ttl:int)->None:
        key=f"fluxfile:active:{subject}"; now=time.time(); result=self.redis.eval("redis.call('ZREMRANGEBYSCORE',KEYS[1],'-inf',ARGV[1]);if redis.call('ZCARD',KEYS[1])>=tonumber(ARGV[2]) then return 0 end;redis.call('ZADD',KEYS[1],ARGV[3],ARGV[4]);redis.call('EXPIRE',KEYS[1],ARGV[5]);return 1",1,key,now,limit,now+ttl,str(job_id),ttl)
        if result!=1:raise TooManyActiveJobsError()
    def release_concurrent(self,subject:str,job_id:UUID)->None:self.redis.zrem(f"fluxfile:active:{subject}",str(job_id))
