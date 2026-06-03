---
layout: post
title:  "memo for fortran commands"
date:   2026-05-30 17:11:00 0100
categories: [tech]
---

After a few days of Fortran programming, I found a record of commonly used Fortran commands need to be kept, as there are subtle differences between Fortran and other languages I have used in the past. 

# Terminal Commands

Simple compilation
```zsh
gfortran my_program.f90 -o my_program
```

Compiling only
```zsh
gfortran -c my_program.f90
``` 

Multi-thread compilation
```zsh
caf my_program.f90 -o my_program
```

Multi-thread execution
```zsh
cafrun -n x ./my_program
```
where x is the number of images

**note**
- `$!` can be used to speed up command typing

# Fortran commands

## Variable initialization

### Initialization statement

single variable initialization
```fortran
data_type :: variable_name
```

Array initialization
```fortran
data_type :: array_name(n)
data_type, dimension(n) :: array_name
```
Finally don't need to indexing with (y, x) lol

Coarray initialization
```fortran
data_type :: array_name(n)[*]
```

Constant initialization
```fortran
data_type, parameter :: const_name = xxx
```

### Variable type

```fortran
integer :: i, n
real :: x
complex :: c = (a, b)
```

**note**
- a constant can be used to initialize other variables
- constant's value must be provided on initialization

specific kind of variable
```fortran
use iso_fortran_env
integer(kind = int32) :: n
```

## Control flow statements

if statement
```fortran
if (condition) !...

if (condition) then
    !...
end if

if (condition) then
    !...
else if (other_condition) then
    !...
end if
```

do loop
```
do n = start, end
    !...
end do

do n = start, end, increment
    !...
end do

!named loop
outer_loop: do j = 1, jm
    inner_loop: do i = 1, im
        !...
    end do inner_loop
end do outer_loop
```

## Fortran program units ###
**program**: the only unit can be invoked as an executable from the operating system
```fortran
program xxx
    implicit none 
    integer :: a, b !declaration of variables

    if a == 1 call add(a, b) !invoke a subroutine
end program
```

**function**: Invoked in expressions, return only one value. 
```fortran
function sum(a,b)
    integer, intent(in) :: a, b
    integer :: sum

    sum = a + b
end function sum
```
OR
```fortran
integer function sum(a,b)
    integer, intent(in) :: a, b
    ! no need to define sum

    sum = a + b
end function sum
```
OR
```fortran
integer function sum(a,b) results(res)
    integer, intent(in) :: a,b

    res = a+b
end function sum
```




**subroutine**: Invoked with a `call` statement.
```fortran
subroutine add(a,b)
    integer, intent(inout) :: a
    integer, intent(in) :: b
    a = a+b
    print *, 'a=', a
end subroutine add
```
### Attributes
**pure** : indicate the function has no side effects. This includes modifying the value of a variable declared outside the procedure. 

**elemental** : allows receiving array arguments in place of scalars

```fortran
pure elemental integer function sum(a,b)
    integer, intent(in) :: a, b
    sum = a+b
end function sum

sum([1,2], 3) ! is valid
sum([1,2], [3,4]) ! is valid
sum([1,2,3], [4,5]) ! is not valid as arrays are not of the same shape.
```

**optional argument**
```fortran
subroutine add(a, b, res, debug)
    integer, intent(in) :: a, b
    integer, intent(out) :: res
    logical, intent(in), optional :: debug

    if (present(debug)) then
        if (debug) then
            !...
        end if
    end if

    res = a + b
end subroutine add
```

## modules

import module
```fortran
use iso_fortran_env, only: int32, real32
```

**rename entity when import**
```fortran
use mod_atmosphere, only: temperature
use mod_ocean, only: temperature_ocean => temperature, velocity_ocean => velocity

```

=> means point to

**Module variable**
```fortran
module mod_circle
    implicit none
    private :: pi
    real, parameter :: pi = 3.14159265
contains
    !...
end module mod_circle
```




# Parallel programming commands

## Parallel programming image indexing

get current image number
```fortran
this_image()
```

get total image number
```fortran
num_images()
```

wait and sync
```fortran
sync all
``` 

## Parallel programming flow statements

embarrassingly parallel iteration
```fortran
do concurrent (i = 1:grid_size)
    !...
end do
```