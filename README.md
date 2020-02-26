# SIMuR
## Source Indexing for MUltiple Repositories
Currently supporting git and svn, and of course multiple repos of both git and
subversion mixed

## For the impatient
- Set the environment variable ***SIMUR_LOCAL_REPO*** to some directory, e.g.

**set SIMUR_LOCAL_REPO=\\\our-server\simur-share\simur_repo_cache**

- Copy script\vcget.cmd to somewhere in your path, edit it to get the right python
and path to vcget.py

**vcget.cmd is what your debugger will call to get the sources**

- Run processPDBs.py 'dir-with-pdbs' 'srcsrv-dir'

**Now the .pdb files will contain instructions how to fetch the correct source files**

    VERSION=1
    VERCTL=SvnGit
    DATETIME=2020-01-29T20:49:57.489168
    SRCSRV: variables -----------------------------------------
    SRCSRVTRG=%vcget_target%
    SRCSRVCMD=%vcget_command%
    VCGET_TARGET=%targ%\%fnbksl%(%var4%)\%var6%\%fnfile%(%var1%)
    VCGET_COMMAND=cmd /c vcget.cmd %var2% "%var3%" "%var4%" %var5% > "%vcget_target%"
    SRCSRV: source files --------------------------------------
    C:\wrk\SIMuR\GitHub\SIMuR\test\src\fromRiouxSVN\trunk\main.c*svn*https://svn.riouxsvn.com/svncat_test1/trunk*main.c*6*3416941a16288d58f71b557766b8d92153aa00f0
    C:\wrk\SIMuR\GitHub\SIMuR\test\src\fromGitHub\gitcat_test2\success2.c*git*https://github.com/NilssonOpel/gitcat_test2.git*success2.c*0e16bc26f4327eb4a1607c42a2c1011e4c670e5d*0e16bc26f4327eb4a1607c42a2c1011e4c670e5d

- Test to call

    vcget.cmd git https://github.com/NilssonOpel/gitcat_test2.git success2.c 0e16bc26f4327eb4a1607c42a2c1011e4c670e5d

or

    vcget.cmd svn https://svn.riouxsvn.com/svncat_test1/trunk main.c 6

Did it not work out?  Then proceed to 'To test it'

## To test it

If you have these installed
- Python 3.6 (ish)
- Visual Studio
- CMake
- Subversion
- Git
- Debugging Tools for Windows, https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/index

then you can easily test it by going to the directory test/ and run ***SetUp.bat***

## How it started

To get the sources from subversion is so easy, just use **svn cat
url@revision**.  But when you work with git you must do something
else.  So my naive idea was to clone all the repositories into a local
directory (set by environment variable ***SIMUR_LOCAL_REPO***) and use
**git show sha1** in the cloned repository.  It started as a git-thing but
then I realized you could mix it with other VCS:s so I added support for mixing
git ***and*** subversion.

Should not be that hard to add Mercurial I guess.

Will be interesting to see how it scales.

## What is source indexing?
It is a Microsoft thing, only available on Windows, there is a nice
introduction here:

https://randomascii.wordpress.com/2011/11/11/source-indexing-is-underused-awesomeness/

or google it, nice keywords: 'srcsrv', 'source indexing',
