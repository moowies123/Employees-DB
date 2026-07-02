create database Employeesdb
go 
use Employeesdb
go 
create table Employees 
(
id int identity primary key,
FirstName varchar(50),
LastName varchar(50),
Salary decimal
)
INSERT INTO Employees
VALUES
('Ahmed','Ali',5000),
('Mohamed','Hassan',7000),
('Sara','Mahmoud',9000);

go
create procedure GetAllEmployees
as
begin
SELECT *
FROM Employees 
end

go 
create procedure etHighSalaryEmployees ( @MinSalary DECIMAL)
as
begin
 SELECT *
    FROM Employees
    WHERE Salary > @MinSalary
end

exec etHighSalaryEmployees 6000 --Test

go

create procedure AddEmployee (@FirstName VARCHAR(50),@LastName VARCHAR(50),@Salary DECIMAL)
as 
begin
 INSERT INTO Employees
 (
 FirstName,
 LastName,
 Salary
 
 )
 values
 (
 @FirstName,
 @LastName,
@Salary
 )
 end

go

--Test
exec AddEmployee 'moamed', 'gamal',50000

go

create table EmployeeLog
(
id int identity primary key,
EmployeeId int,
Action VARCHAR (50),
ActionDate DATETIME
)
go

create trigger TR_Employee_Insert
on Employees
after insert 
as
begin 

insert into EmployeeLog
(
EmployeeId,
Action,
ActionDate
)
select 
Id,
'INSERT',
GETDATE()
FROM inserted
end

--Test Trigger 
insert into Employees 
(
FirstName,
LastName,
Salary
)
values
(
'Amir','abdelazeem',50000
)
go

select * 
from Employees 

select * 
from EmployeeLog
