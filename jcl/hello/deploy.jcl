//OSEHDEP  JOB (OSE),'OSE-004 DEPLOY',CLASS=A,MSGCLASS=A,
//             MSGLEVEL=(1,1),USER={USER},PASSWORD={PASS},
//             REGION=8192K
//* OSE-004 deploy. Template, filled by tests/guest/hello/hello_guest.py:
//* the XMIT's raw 80-byte EBCDIC records replace the XMIT marker card, and the
//* whole deck goes to the EBCDIC reader (001A, port 3506). The same
//* method upstream sysgen uses (mvslovers.py stage_parts + RECEIVE).
//* No FTPD and no mvsMF (research 2026-11-26-toolchain T-6).
//DELOLD   EXEC PGM=IDCAMS
//SYSPRINT DD  SYSOUT=*
//SYSIN    DD  *
  DELETE {HLQ}.OSE.HELLO.XMIT NONVSAM SCRATCH PURGE
  DELETE {HLQ}.OSE.LOAD NONVSAM SCRATCH PURGE
  SET MAXCC=0
/*
//* Fail closed: the target must be gone before RECEIVE, so a stale
//* library can never pass for a fresh deploy. LISTCAT of a missing
//* entry ends with CC 4 (IDC3012I); CC 0 means the delete did not work.
//GONE     EXEC PGM=IDCAMS
//SYSPRINT DD  SYSOUT=*
//SYSIN    DD  *
  LISTCAT ENTRIES({HLQ}.OSE.LOAD)
/*
//STAGE    EXEC PGM=IEBGENER,COND=((0,NE,DELOLD),(4,NE,GONE))
//SYSPRINT DD  SYSOUT=*
//SYSIN    DD  DUMMY
//SYSUT2   DD  DSN={HLQ}.OSE.HELLO.XMIT,DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,SPACE=(TRK,(10,10),RLSE),
//             DCB=(RECFM=FB,LRECL=80,BLKSIZE=3120)
//SYSUT1   DD  DATA,DLM={DLM}
{XMIT}
{DLM}
//* MVS ignores a COND test that names a bypassed step, so every later
//* step repeats the DELOLD and GONE tests itself (review R04-2).
//RECV     EXEC PGM=IKJEFT01,DYNAMNBR=20,
//         COND=((0,NE,DELOLD),(4,NE,GONE),(0,NE,STAGE))
//SYSTSPRT DD  SYSOUT=*
//SYSTSIN  DD  *
  RECEIVE INDSN('{HLQ}.OSE.HELLO.XMIT') -
    VOLUME('{VOLUME}') -
    DATASET('{HLQ}.OSE.LOAD')
/*
//CLEANUP  EXEC PGM=IDCAMS,
//         COND=((0,NE,DELOLD),(4,NE,GONE),(0,NE,STAGE),(0,NE,RECV))
//SYSPRINT DD  SYSOUT=*
//SYSIN    DD  *
  DELETE {HLQ}.OSE.HELLO.XMIT NONVSAM SCRATCH PURGE
/*
//
