#!/bin/bash

# NOTE: Place this in /scratch
for i in 1 2 3 4 5
do
   /bin/bash ~/near/isaacgymenvs/send_db_job.sh
   echo "Job $i Sent!"
   echo "-----"
done