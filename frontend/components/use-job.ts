"use client";
import {useEffect,useState} from "react";
import {installationRequest} from "../lib/installations";

export type Job={id:string;status:"queued"|"running"|"succeeded"|"failed";message?:string};

/** Follows a queued worker job until it finishes. */
export function useJob(csrfToken:string){
  const [job,setJob]=useState<Job|null>(null);
  const [error,setError]=useState("");
  useEffect(()=>{
    if(!job || !["queued","running"].includes(job.status))return;
    let cancelled=false;
    const timer=setInterval(()=>{installationRequest<Job>(`/jobs/${job.id}`,csrfToken).then(data=>{if(!cancelled){setJob(data);setError("");}}).catch(failure=>{if(!cancelled)setError(failure.message);});},2500);
    return()=>{cancelled=true;clearInterval(timer);};
  },[job,csrfToken]);
  return {job,setJob,error};
}

