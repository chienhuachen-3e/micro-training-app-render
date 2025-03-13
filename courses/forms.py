from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Program, Topic, Lesson, Quiz, QuizChoice, Enrollment, QuizResponse, QuizChoice

User = get_user_model()

class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = ['title', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ['title', 'description', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['title', 'content', 'video_url', 'order']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 6}),
        }

class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'question', 'quiz_type', 'points']
        widgets = {
            'question': forms.Textarea(attrs={'rows': 4}),
        }

class QuizChoiceFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        has_correct = False
        for form in self.forms:
            if not form.is_valid() or form.cleaned_data.get('DELETE'):
                continue
            if form.cleaned_data.get('is_correct'):
                has_correct = True
                break
        if not has_correct and self.instance.quiz_type == 'MCQ':
            raise forms.ValidationError("Please mark at least one choice as correct.")

QuizChoiceFormSet = forms.inlineformset_factory(
    Quiz,
    QuizChoice,
    fields=['choice_text', 'is_correct'],
    extra=4,
    can_delete=True,
    formset=QuizChoiceFormSet
)

class QuizResponseForm(forms.ModelForm):
    selected_choice = forms.ModelChoiceField(
        queryset=QuizChoice.objects.none(),
        empty_label=None,
        widget=forms.RadioSelect,
        required=False,
        label='Select your answer'
    )
    text_response = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label='Your answer'
    )

    class Meta:
        model = QuizResponse
        fields = ['selected_choice', 'text_response']

    def __init__(self, *args, quiz=None, **kwargs):
        super().__init__(*args, **kwargs)
        if quiz:
            if quiz.quiz_type == 'MCQ':
                choices = quiz.choices.all()
                print(f"Debug: Found {choices.count()} choices for quiz {quiz.id}")
                self.fields['selected_choice'].queryset = choices
                self.fields['selected_choice'].required = True
                self.fields['selected_choice'].label_from_instance = lambda obj: obj.choice_text
                del self.fields['text_response']
            else:  # OPEN
                self.fields['text_response'].required = True
                del self.fields['selected_choice']

class QuizGradingForm(forms.ModelForm):
    class Meta:
        model = QuizResponse
        fields = ['points_earned', 'grading_comment']
        widgets = {
            'grading_comment': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_points_earned(self):
        points = self.cleaned_data['points_earned']
        max_points = self.instance.quiz.points
        if points > max_points:
            raise forms.ValidationError(f"Points cannot exceed maximum points ({max_points})")
        return points

class EnrollmentManageForm(forms.Form):
    department = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by username or email'
        })
    )

    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_manager=False),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get unique departments
        departments = User.objects.exclude(department='').values_list(
            'department', flat=True).distinct()
        self.fields['department'].choices = [('', 'All Departments')] + [
            (dept, dept) for dept in departments
        ]

    def filter_users(self, search_query='', department=''):
        users = User.objects.filter(is_manager=False)
        
        if department:
            users = users.filter(department=department)
            
        if search_query:
            users = users.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query)
            )
            
        return users

class CourseSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search courses...'
        })
    )
    
    creator = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    sort_by = forms.ChoiceField(
        choices=[
            ('newest', 'Newest First'),
            ('oldest', 'Oldest First'),
        ],
        required=False,
        initial='newest',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    progress = forms.ChoiceField(
        choices=[
            ('', 'All Courses'),
            ('not_started', 'Not Started'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        creator_choices = kwargs.pop('creator_choices', [])
        super().__init__(*args, **kwargs)
        self.fields['creator'].choices = [('', 'All Creators')] + [
            (creator.id, creator.username) for creator in creator_choices
        ]