project(TestGitCat)

# Just go on the defaults and then use RelWithDebInfo to test

set(Sources
  fromRiouxSVN/trunk/main.c
  fromRiouxSVN/trunk/success1.c
  fromRiouxSVN/trunk/svn_subdir/success4.c
  fromGitHub/gitcat_test2/success2.c
  fromGitHub/gitcat_test1/success3.c
  fromGitHub/gitcat_test1/other.c
  fromGitHub/gitcat_test1/dummy.c
  fromGitHub/gitcat_test1/subdir/file_in_subdir.c
)

add_executable(TestGitCat ${Sources})