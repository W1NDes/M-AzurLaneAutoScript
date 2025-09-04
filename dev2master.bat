@echo off
chcp 65001
echo 开始将dev分支合并到master分支...

REM 检查是否有未提交的更改
git diff-index --quiet HEAD --
if %ERRORLEVEL% neq 0 (
    echo 发现未提交的更改，正在stash...
    git stash push -m "Auto stash before merge to master"
    set NEED_POP=1
) else (
    set NEED_POP=0
)

REM 切换到dev分支并更新
git checkout dev
git pull origin dev

REM 切换到master分支并合并
git checkout master
git pull origin master
git merge dev --no-ff -m "Merge dev branch to master"
git push origin master

REM 切回dev分支
git checkout dev

REM 如果之前有stash，则恢复
if %NEED_POP%==1 (
    echo 恢复之前的更改...
    git stash pop
)

echo 合并完成！
pause
