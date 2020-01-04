# SIMuR
## Source Indexing for MUltiple Repositories

*Note: this is currently just a test of concept*

If you have
- Python 3.6 (ish)
- Visual Studio
- CMake
- Subversion
- Git
- Debugging Tools for Windows, https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/index

then you can go to /test and run SetUp.bat - if you are lucky, the implementation is still quite naive

## How it started
To get the sources from subversion is so easy, just use **svn cat <url>@revision**.  But when you work with git you must do something else.  So my naive idea was to clone all the repositories into a local directory and use **git show <sha1>** in the cloned repository.  It started as a git-thing but then I realized you could mix it with other VCS so I added support for mixed git ***and*** subversion.  Should not be that hard to add Mercurial I guess.
  
Will be interesting to see how it scales.
  
## What is source indexing?
It is a Microsoft thing, only available on Windows, there is a nice introduction here: https://randomascii.wordpress.com/2011/11/11/source-indexing-is-underused-awesomeness/  
or google it
