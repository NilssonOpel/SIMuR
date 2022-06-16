# SIMuR
## Source Indexing for MUltiple Repositories
Currently supporting mixed repos of git and svn

Works with any gitserver: GitHub, GitLab, your private git server or whatever


## For the impatient
- Set the environment variable ***SIMUR_REPO_CACHE*** to some directory, e.g.

> **set SIMUR_REPO_CACHE=\\\our-server\simur-share\simur_repo_cache**

if you do not set it, SIMuR will use the path **C:\simur_repo** by default

- Copy script\vcget.cmd to somewhere in your path, edit to get the right
python and correct path to script\vcget.py

**vcget.cmd is what your debugger will call to get the sources**

- Test for GitLab by calling
> vcget.cmd git https://gitlab.com/luckshot/ansible-workstation.git README.md d18a86301959

- Test for GitHub by calling
> vcget.cmd git https://github.com/NilssonOpel/gitcat_test2.git success2.c 0e16bc26f432

- Test for BitBucket by calling
> vcget.cmd git https://bitbucket.org/bitbucket/cloudide.git codio.json ac9aa7f4dc

You should see the content of the file in question (README.md, success2.c or
codio.json), and you will get a clone of the git repo in the folder given by
SIMUR_REPO_CACHE (or C:\simur_repo if you did not set it)

- Test for Subversion:
> vcget.cmd svn https://svn.riouxsvn.com/svncat_test1/trunk main.c 6

For Subversion, SIMuR do not populate the SIMUR_REPO_CACHE, it will use
'svn cat' directly from the subversion server, i.e. vcget will eventually call
> svn cat https://svn.riouxsvn.com/svncat_test1/trunk/main.c@6

- Test on your own sources
> processPDBs.py 'dir-with-pdbs' 'srcsrv-dir'

or better yet, use indexPDBs.py directly
> indexPDBs.py -h

**Now the .pdb files should contain instructions how to fetch the correct source
files, which you can see by running**

> "C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\srcsrv\pdbstr.exe" -r -p:TestGitCat.pdb -s:srcsrv

and in the PDB you should find a passage that looks something like this

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

Did it not work out?  Then try:

## To test it

If you have these installed
- Python 3.6 (ish)
- Visual Studio
- CMake
- Subversion
- Git
- Debugging Tools for Windows,
https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/index

You need to set up Visual Studio to enable source server support, you can
read about how here
http://www.symbolsource.org/Public/Home/VisualStudio
and
https://docs.microsoft.com/en-us/visualstudio/debugger/general-debugging-options-dialog-box?view=vs-2019

*There is an issue with Win10 that JIT debugging is by default disabled.  Since
the test program has a crash, JIT debugging has to be enabled for the test to
work.  The crash is to get into the debugger and to show that the debugger can
pick up the remote sources*.

To enable JIT debugging please take a look at
https://docs.microsoft.com/en-us/visualstudio/debugger/debug-using-the-just-in-time-debugger?view=vs-2019

- Test it by going to the directory test/ and run ***TestExe.bat*** or
***TestWithLib.bat***

It should eventually break into your debugger if you have JIT Debugging enabled,
see above


## How it started

To get the source code from subversion is easy, just use **svn cat
url@revision**.  But when you work with git you must do something
else.  So my naive idea was to clone all the repositories into a local
directory (set by environment variable ***SIMUR_REPO_CACHE***) and use
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
