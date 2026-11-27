//OSEHRUN  JOB (OSE),'OSE-004 RUN',CLASS=A,MSGCLASS=A,
//             MSGLEVEL=(1,1),USER={USER},PASSWORD={PASS},
//             REGION=8192K
//* OSE-004 acceptance 3: the step RC must equal the value in PARM, and
//* SYSPRINT (libc370 stdout, "*SYSPRINT") must hold the expected line.
//RC0      EXEC PGM=HELLO
//STEPLIB  DD  DSN={HLQ}.OSE.LOAD,DISP=SHR
//SYSPRINT DD  SYSOUT=*
//RC4      EXEC PGM=HELLO,PARM='4'
//STEPLIB  DD  DSN={HLQ}.OSE.LOAD,DISP=SHR
//SYSPRINT DD  SYSOUT=*
//
