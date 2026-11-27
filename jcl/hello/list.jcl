//OSEHLST  JOB (OSE),'OSE-004 LIST',CLASS=A,MSGCLASS=A,
//             MSGLEVEL=(1,1),USER={USER},PASSWORD={PASS},
//             REGION=8192K
//* OSE-004 acceptance 2: confirm the deployed member with a listing job,
//* independent of the deploy job's return codes.
//LISTDS   EXEC PGM=IKJEFT01
//SYSTSPRT DD  SYSOUT=*
//SYSTSIN  DD  *
  LISTDS '{HLQ}.OSE.LOAD' MEMBERS
/*
//
